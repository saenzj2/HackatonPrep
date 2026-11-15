"""Field indicators per calendar month from a daily series: temperature, rain, dry spells.

Pure functions, plain floats in (NaN = missing day), dataclasses out. Thresholds and how each
indicator treats missing days are listed in docs/indicators.md.

Heat-stress and frost days need the day's true maximum and minimum temperature. A daily MEAN
(NASA POWER `T2M`) hides both: a day averaging 20 °C can still peak above 30 °C or drop near
freezing at dawn. So those two indicators are only computed when daily extrema are passed in,
and are `None` otherwise. They are never estimated from the mean.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from app.domain.erosion import HEAVY_RAIN_MM
from app.domain.suitability import FROST_C
from app.errors import DomainInvariantError

# A day with < 1 mm is dry: the ETCCDI wet-day threshold (used by its CDD and R1mm indices).
DRY_DAY_MM = 1.0
# Extreme rain = the erosion module's heavy-rain day (>= 30 mm): both count the same days.
EXTREME_RAIN_MM = HEAVY_RAIN_MM
# Placeholder: daily max >= 35 °C is a commonly cited heat-stress level for flowering in maize and
# beans. Not crop-specific. Needs an agro-logic review before it is scored (decisions.md).
HEAT_STRESS_MAX_C = 35.0
# Air frost: daily min at or below 0 °C (same value as suitability.FROST_C). Ground frost can occur
# with a 2 m minimum of a few °C above zero, so this undercounts frost risk on clear nights.
FROST_MIN_C = FROST_C


@dataclass(frozen=True)
class MonthlyIndicators:
    """Indicators for one calendar month of the series.

    Each indicator only uses the days that have data for its variable; the `*_days` counts say
    how many that was, so a month with gaps is visible instead of silently looking drier or cooler.
    A value is `None` when its variable has no data at all in the month (or, for heat-stress and
    frost days, when no daily max / min series was given).
    """

    year: int
    month: int
    days: int  # days of this month present in the series (may be a partial month)
    temperature_days: int  # days with a daily mean temperature
    rainfall_days: int  # days with a rainfall value
    extrema_days: int  # days with both daily max and min (0 when no extrema were given)
    mean_temperature_c: float | None  # mean of the daily means
    total_rainfall_mm: float | None  # sum over rainfall_days only (undercount with gaps)
    dry_days: int | None  # days with rainfall < DRY_DAY_MM
    longest_dry_spell_days: int | None  # longest run of consecutive dry days inside the month
    extreme_rain_days: int | None  # days with rainfall >= EXTREME_RAIN_MM
    heat_stress_days: int | None  # days with max >= HEAT_STRESS_MAX_C
    frost_days: int | None  # days with min <= FROST_MIN_C


def _present(values: Sequence[float]) -> list[float]:
    return [v for v in values if not math.isnan(v)]


def _longest_dry_spell(rainfall_mm: Sequence[float]) -> int:
    """Longest run of consecutive dry days. A missing day ends the run: we can't call it dry."""
    longest = run = 0
    for v in rainfall_mm:
        run = run + 1 if not math.isnan(v) and v < DRY_DAY_MM else 0
        longest = max(longest, run)
    return longest


def _month_indicators(
    year: int,
    month: int,
    *,
    temperature_c: Sequence[float],
    rainfall_mm: Sequence[float],
    extrema_c: Sequence[tuple[float, float]] | None,
) -> MonthlyIndicators:
    temps = _present(temperature_c)
    rain = _present(rainfall_mm)
    extrema = [
        (hi, lo) for hi, lo in (extrema_c or ()) if not math.isnan(hi) and not math.isnan(lo)
    ]
    has_extrema = bool(extrema)
    return MonthlyIndicators(
        year=year,
        month=month,
        days=len(rainfall_mm),
        temperature_days=len(temps),
        rainfall_days=len(rain),
        extrema_days=len(extrema),
        mean_temperature_c=sum(temps) / len(temps) if temps else None,
        total_rainfall_mm=sum(rain) if rain else None,
        dry_days=sum(1 for v in rain if v < DRY_DAY_MM) if rain else None,
        longest_dry_spell_days=_longest_dry_spell(rainfall_mm) if rain else None,
        extreme_rain_days=sum(1 for v in rain if v >= EXTREME_RAIN_MM) if rain else None,
        heat_stress_days=(
            sum(1 for hi, _ in extrema if hi >= HEAT_STRESS_MAX_C) if has_extrema else None
        ),
        frost_days=sum(1 for _, lo in extrema if lo <= FROST_MIN_C) if has_extrema else None,
    )


def monthly_indicators(
    *,
    dates: Sequence[date],
    temperature_c: Sequence[float],
    rainfall_mm: Sequence[float],
    temperature_max_c: Sequence[float] | None = None,
    temperature_min_c: Sequence[float] | None = None,
) -> tuple[MonthlyIndicators, ...]:
    """One MonthlyIndicators per calendar month in the series, oldest first.

    All sequences are aligned day by day with `dates` (strictly increasing, one entry per day).
    temperature_c is the daily MEAN (°C), rainfall_mm the day's total (mm). Pass the daily
    maximum and minimum (°C) together to get heat-stress and frost days; with only the mean,
    those stay None. Dry spells are cut at month boundaries, so a spell crossing two months
    counts in each month separately.
    """
    if (temperature_max_c is None) != (temperature_min_c is None):
        raise DomainInvariantError("Pass both temperature_max_c and temperature_min_c, or neither")
    series = [temperature_c, rainfall_mm, temperature_max_c or (), temperature_min_c or ()]
    expected = [len(dates)] * 2 + [len(dates) if temperature_max_c is not None else 0] * 2
    if [len(s) for s in series] != expected:
        raise DomainInvariantError("Daily series must have one value per date")
    if any(b <= a for a, b in itertools.pairwise(dates)):
        raise DomainInvariantError("Dates must be strictly increasing")

    by_month: dict[tuple[int, int], list[int]] = {}
    for i, d in enumerate(dates):
        by_month.setdefault((d.year, d.month), []).append(i)

    def pick(values: Sequence[float], idx: list[int]) -> list[float]:
        return [values[i] for i in idx]

    return tuple(
        _month_indicators(
            year,
            month,
            temperature_c=pick(temperature_c, idx),
            rainfall_mm=pick(rainfall_mm, idx),
            extrema_c=(
                None
                if temperature_max_c is None or temperature_min_c is None
                else [(temperature_max_c[i], temperature_min_c[i]) for i in idx]
            ),
        )
        for (year, month), idx in by_month.items()
    )
