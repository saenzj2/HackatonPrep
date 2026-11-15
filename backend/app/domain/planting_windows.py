"""Planting windows: in which months is it good to sow a crop at this location?

For every possible sowing month (Jan..Dec) the crop is scored over the months it spends in the
field (its cycle, rounded up to whole months, wrapping into the next year), with the same
crop_season_fit() used for rotations. Consecutive good sowing months form a window.

The rotation model keeps its fixed seasons (config/mvp.yaml). Windows are extra information:
they show the best sowing time per crop and can be used to check the configured seasons.
"""

from __future__ import annotations

import calendar
import math
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.models import (
    MONTHS,
    CropProfile,
    CropSeasonFit,
    MonthlyClimate,
    Season,
    SoilConditions,
    Weights,
)
from app.domain.suitability import (
    DAYS_PER_MONTH,
    MARGINAL_SCORE,
    crop_season_fit,
    season_climate,
)

# A sowing month is good when its overall score reaches this AND no variable is marginal
# (< MARGINAL_SCORE). The overall score averages climate, water and soil, so one factor near its
# limit (e.g. rainfall 0.08) can still give 0.85; the second condition stops that. Placeholder.
GOOD_SOWING_SCORE = 0.8


@dataclass(frozen=True)
class SowingMonth:
    sowing_month: int  # 1..12
    fit: CropSeasonFit  # fit.season.months = the months the crop is in the field

    @property
    def score(self) -> float:
        return self.fit.score

    def is_good(self, min_score: float = GOOD_SOWING_SCORE) -> bool:
        """High overall score and no single factor near its limit."""
        return self.score >= min_score and all(
            v >= MARGINAL_SCORE for v in self.fit.variable_scores.values()
        )


@dataclass(frozen=True)
class PlantingWindow:
    """Consecutive good sowing months, e.g. first_month=11, last_month=1 → sow Nov to Jan."""

    first_month: int
    last_month: int
    best_month: int
    best_score: float


def cycle_months(sowing_month: int, cycle_days: int) -> tuple[int, ...]:
    """Months in the field: sowing month plus enough months to cover the cycle (wraps the year)."""
    n = min(MONTHS, max(1, math.ceil(cycle_days / DAYS_PER_MONTH)))
    return tuple((sowing_month - 1 + i) % MONTHS + 1 for i in range(n))


def sowing_calendar(
    crop: CropProfile,
    *,
    climate: MonthlyClimate,
    soil: SoilConditions,
    weights: Weights,
    variables: Sequence[str],
) -> tuple[SowingMonth, ...]:
    """The crop's fit for each of the 12 sowing months, January first."""
    w = weights.normalized()
    result = []
    for month in range(1, MONTHS + 1):
        season = Season(
            f"sown in {calendar.month_abbr[month]}", cycle_months(month, crop.cycle_days)
        )
        fit = crop_season_fit(crop, season_climate(climate, season), soil, w, variables)
        result.append(SowingMonth(sowing_month=month, fit=fit))
    return tuple(result)


def planting_windows(
    months: Sequence[SowingMonth], min_score: float = GOOD_SOWING_SCORE
) -> tuple[PlantingWindow, ...]:
    """Runs of consecutive good sowing months (SowingMonth.is_good). A run can wrap Dec → Jan."""
    good = [m.is_good(min_score) for m in months]
    if not any(good):
        return ()
    if all(good):
        best = max(months, key=lambda m: m.score)
        return (PlantingWindow(1, MONTHS, best.sowing_month, best.score),)
    start = good.index(False)  # begin scanning after a bad month so no run is split at Dec/Jan
    runs: list[list[SowingMonth]] = []
    for i in range(1, MONTHS + 1):
        m = months[(start + i) % MONTHS]
        if m.is_good(min_score):
            if runs and _next(runs[-1][-1]) == m.sowing_month:
                runs[-1].append(m)
            else:
                runs.append([m])
    windows = []
    for run in runs:
        best = max(run, key=lambda m: m.score)
        windows.append(
            PlantingWindow(run[0].sowing_month, run[-1].sowing_month, best.sowing_month, best.score)
        )
    return tuple(sorted(windows, key=lambda w: w.first_month))


def _next(m: SowingMonth) -> int:
    return m.sowing_month % MONTHS + 1
