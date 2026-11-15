"""Planting windows: in which months is it good to sow a crop at this location?

For every possible sowing month (Jan..Dec) the crop is scored over the months it spends in the
field (its cycle, rounded up to whole months, wrapping into the next year), with the same
crop_season_fit() used for rotations. Consecutive good sowing months form a window.

The rotation model keeps its fixed seasons (config/mvp.yaml). Windows are extra information:
they show the best sowing time per crop and can be used to check the configured seasons.

Only variables that change by month decide a window. Soil pH is the same in every month at a
location, so it can't shape a window; it would only veto all 12 months (agro-logic review). It is
reported once per crop instead (fixed_limits); a pH outside the crop's absolute range still
leaves no window, because the crop can't grow there in any month.

Waterlogging never removes a month either: ~9 km monthly SMAP data can't see a field's drainage,
slope or raised beds. It still lowers the crop score (rotations feel it) and flags the month
(fit.waterlogging_warning). Agro-logic review 2026-11-15.
"""

from __future__ import annotations

import calendar
import math
from collections.abc import Sequence
from dataclasses import dataclass, replace

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
    CATEGORY_OF,
    DAYS_PER_MONTH,
    MARGINAL_SCORE,
    crop_season_fit,
    season_climate,
    weighted_score,
)

# A sowing month is good when its window score reaches this AND no month-varying variable is
# marginal (< MARGINAL_SCORE). The score averages categories, so one factor near its limit (e.g.
# rainfall 0.08) can still give 0.85; the second condition stops that. Placeholder (0.7 and 0.8
# gave the same San Carlos windows; agro-logic review 2026-11-15).
GOOD_SOWING_SCORE = 0.8
# Variables with the same value in every month at a location: they don't decide windows.
FIXED_VARIABLES = frozenset({"soil_ph"})

# Dry-month check (agro-logic review 2026-11-15): the cycle's rain total can hide dry months
# (maize sown in March: 29 and 76 mm, then May's rains make the total look fine). Every month in
# the field except the last (harvest, where dry weather is wanted) is checked: its rain is scored
# on a ramp from rain_abs_min / (n + DIVISOR_EXTRA) (0) to rain_opt_min / (n + DIVISOR_EXTRA) (1),
# n = months in the field, as Recocrop splits EcoCrop ranges by month. The driest checked month
# must score >= MARGINAL_SCORE (maize and beans pass at ~100 mm, Oldeman's wet-month bar). It only
# decides good sowing months; it isn't averaged into the crop score. Placeholder.
DIVISOR_EXTRA = 1


@dataclass(frozen=True)
class DryMonth:
    """The driest month the crop spends in the field before the harvest month, and how it scores."""

    month: int  # 1..12
    rainfall_mm: float  # long-term mean rain in that month
    limit_mm: float  # score 0 at or below this (rain_abs_min / (n + DIVISOR_EXTRA))
    optimal_mm: float  # score 1 from this (rain_opt_min / (n + DIVISOR_EXTRA))
    score: float  # 0..1; the sowing month is good only if this is >= MARGINAL_SCORE

    @property
    def pass_mm(self) -> float:
        """Rain at which the ramp reaches MARGINAL_SCORE (where the check passes)."""
        return self.limit_mm + MARGINAL_SCORE * (self.optimal_mm - self.limit_mm)


@dataclass(frozen=True)
class SowingMonth:
    sowing_month: int  # 1..12
    fit: CropSeasonFit  # fit.season.months = the months the crop is in the field
    # Score that decides the window: without the fixed variables (FIXED_VARIABLES) and without the
    # waterlogging factor. None = same as fit.score.
    window_score: float | None = None
    dry_month: DryMonth | None = None  # None = nothing to check (one-month cycle)

    @property
    def score(self) -> float:
        return self.fit.score

    def is_good(self, min_score: float = GOOD_SOWING_SCORE) -> bool:
        """High score on the month-varying variables and none of them near its limit."""
        varying = [v for k, v in self.fit.variable_scores.items() if k not in FIXED_VARIABLES]
        score = self.score if self.window_score is None else self.window_score
        dry_ok = self.dry_month is None or self.dry_month.score >= MARGINAL_SCORE
        return score >= min_score and dry_ok and all(v >= MARGINAL_SCORE for v in varying)


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
        result.append(
            SowingMonth(
                sowing_month=month,
                fit=fit,
                window_score=_window_score(fit, w),
                dry_month=dry_month_check(crop, climate, season.months),
            )
        )
    return tuple(result)


def dry_month_check(
    crop: CropProfile, climate: MonthlyClimate, months: tuple[int, ...]
) -> DryMonth | None:
    """Score the driest month in the field, harvest month excluded. None for a one-month cycle."""
    checked = months[:-1]
    if not checked:
        return None
    divisor = len(months) + DIVISOR_EXTRA
    limit = crop.rainfall_mm.abs_min / divisor
    optimal = crop.rainfall_mm.opt_min / divisor
    driest = min(checked, key=lambda m: climate.rainfall_mm[m - 1])
    rain = climate.rainfall_mm[driest - 1]
    if optimal <= limit:  # no ramp in the crop's range: pass/fail at the limit
        score = 1.0 if rain > limit else 0.0
    else:
        score = min(1.0, max(0.0, (rain - limit) / (optimal - limit)))
    return DryMonth(month=driest, rainfall_mm=rain, limit_mm=limit, optimal_mm=optimal, score=score)


def _window_score(fit: CropSeasonFit, weights: Weights) -> float:
    """fit.score without the waterlogging factor, and without the soil category when it only holds
    fixed variables. Still 0 when any variable (fixed or not) is outside its absolute range: the
    crop fails there."""
    if fit.score == 0:
        return 0.0
    soil_vars = {k for k in fit.variable_scores if CATEGORY_OF[k] == "soil"}
    if not soil_vars or not soil_vars <= FIXED_VARIABLES:
        return fit.score / fit.waterlogging_factor  # the factor is > 0 by construction
    return weighted_score(replace(fit.categories, soil=None), weights)


def fixed_limits(months: Sequence[SowingMonth]) -> dict[str, float]:
    """Fixed variables (FIXED_VARIABLES) that score below 1 for this crop, with their score.

    They're the same in every sowing month, so they're reported once per crop, not per month.
    """
    if not months:
        return {}
    scores = months[0].fit.variable_scores
    return {k: v for k, v in scores.items() if k in FIXED_VARIABLES and v < 1}


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
