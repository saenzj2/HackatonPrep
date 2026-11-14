"""Erosion risk: local slope (SRTM) → terrain risk, daily rainfall → rainfall risk, then combined.

All levels are 0 (low), 1 (medium), 2 (high). Pure functions, plain floats in, dataclasses out.
Thresholds are explainable placeholders, not calibrated soil-loss estimates (e.g. RUSLE). Changing
them needs a docs/decisions.md entry, ideally after an agro-logic review.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum

from app.domain.models import TerrainSample
from app.errors import DomainInvariantError

# Slope classes for terrain susceptibility, from the task spec (placeholder until reviewed).
SLOPE_MEDIUM_PCT = 5.0  # below this, runoff is slow: low erosion susceptibility
SLOPE_HIGH_PCT = 15.0  # above this, high susceptibility
REFERENCE_PERIOD_DAYS = 30  # heavy-rain counts are expressed per 30 days, so any period compares
HEAVY_RAIN_MM = 30.0  # a day with >= 30 mm counts as heavy rain (task spec)


class ErosionRisk(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2


@dataclass(frozen=True)
class RainfallThresholds:
    """Rainfall risk thresholds. Placeholders, override per call to experiment.

    Each indicator gives a level (≥ medium → 1, ≥ high → 2) and the rainfall risk is the worst one.
    Rates (mm/day, days per 30 days) instead of totals, so a 1-month and a 1-year period
    are judged on the same scale.
    """

    heavy_rain_mm: float = HEAVY_RAIN_MM
    avg_daily_medium_mm: float = 4.0  # ~1460 mm/year
    avg_daily_high_mm: float = 8.0  # ~2900 mm/year, wet Caribbean / Pacific south slopes
    heavy_days_per_30d_medium: float = 1.0
    heavy_days_per_30d_high: float = 3.0
    max_daily_medium_mm: float = 50.0
    max_daily_high_mm: float = 100.0  # a single storm of this size can strip bare soil

    def __post_init__(self) -> None:
        pairs = (
            (self.avg_daily_medium_mm, self.avg_daily_high_mm),
            (self.heavy_days_per_30d_medium, self.heavy_days_per_30d_high),
            (self.max_daily_medium_mm, self.max_daily_high_mm),
        )
        if self.heavy_rain_mm <= 0 or any(not 0 <= med <= high for med, high in pairs):
            raise DomainInvariantError(
                f"Rainfall thresholds must satisfy 0 <= medium <= high: {self}"
            )


DEFAULT_RAINFALL_THRESHOLDS = RainfallThresholds()


@dataclass(frozen=True)
class RainfallSummary:
    total_mm: float
    avg_daily_mm: float
    heavy_rain_days: int
    max_daily_mm: float
    valid_days: int  # days with data; missing (NaN) days are left out of every indicator


@dataclass(frozen=True)
class ErosionAssessment:
    elevation_m: float
    slope_pct: float
    terrain_erosion_risk: ErosionRisk
    rainfall: RainfallSummary
    rainfall_erosion_risk: ErosionRisk
    combined_erosion_risk: ErosionRisk


def slope_pct(terrain: TerrainSample) -> float:
    """Local slope in percent (rise / run × 100) from central differences.

    The centre point itself doesn't enter the gradient: each axis uses the two neighbours,
    2 × spacing apart. 100 % = 45°.
    """
    dz_dx = (terrain.east_m - terrain.west_m) / (2 * terrain.spacing_ew_m)
    dz_dy = (terrain.north_m - terrain.south_m) / (2 * terrain.spacing_ns_m)
    return 100 * math.hypot(dz_dx, dz_dy)


def terrain_risk(slope: float) -> ErosionRisk:
    """< 5 % low, 5 to 15 % medium (both ends included), > 15 % high."""
    if slope < SLOPE_MEDIUM_PCT:
        return ErosionRisk.LOW
    if slope <= SLOPE_HIGH_PCT:
        return ErosionRisk.MEDIUM
    return ErosionRisk.HIGH


def summarize_rainfall(
    daily_rainfall_mm: Sequence[float], *, heavy_rain_mm: float = HEAVY_RAIN_MM
) -> RainfallSummary:
    """Totals and extremes over the days that have data (NaN = missing day, skipped)."""
    days = [v for v in daily_rainfall_mm if not math.isnan(v)]
    if not days:
        raise DomainInvariantError("summarize_rainfall needs at least one day with data")
    total = sum(days)
    return RainfallSummary(
        total_mm=total,
        avg_daily_mm=total / len(days),
        heavy_rain_days=sum(1 for v in days if v >= heavy_rain_mm),
        max_daily_mm=max(days),
        valid_days=len(days),
    )


def _level(value: float, medium: float, high: float) -> ErosionRisk:
    if value >= high:
        return ErosionRisk.HIGH
    if value >= medium:
        return ErosionRisk.MEDIUM
    return ErosionRisk.LOW


def rainfall_risk(
    summary: RainfallSummary, thresholds: RainfallThresholds = DEFAULT_RAINFALL_THRESHOLDS
) -> ErosionRisk:
    """Worst of three indicators: average intensity, how often it pours, the biggest storm."""
    heavy_per_30d = summary.heavy_rain_days * REFERENCE_PERIOD_DAYS / summary.valid_days
    return max(
        _level(summary.avg_daily_mm, thresholds.avg_daily_medium_mm, thresholds.avg_daily_high_mm),
        _level(
            heavy_per_30d, thresholds.heavy_days_per_30d_medium, thresholds.heavy_days_per_30d_high
        ),
        _level(summary.max_daily_mm, thresholds.max_daily_medium_mm, thresholds.max_daily_high_mm),
    )


def combined_risk(terrain: ErosionRisk, rainfall: ErosionRisk) -> ErosionRisk:
    """Slope decides the base level; heavy rain can raise it one step, never lower it.

    Water erosion needs both runoff (slope) and rain to drive it:
        rainfall →  low  medium  high
        flat (0)     0     0      1
        medium (1)   1     1      2
        steep (2)    2     2      2
    """
    return ErosionRisk(max(terrain, min(ErosionRisk.HIGH, terrain + rainfall - 1)))


def assess_erosion(
    *,
    terrain: TerrainSample,
    daily_rainfall_mm: Sequence[float],
    thresholds: RainfallThresholds = DEFAULT_RAINFALL_THRESHOLDS,
) -> ErosionAssessment:
    slope = slope_pct(terrain)
    terrain_level = terrain_risk(slope)
    summary = summarize_rainfall(daily_rainfall_mm, heavy_rain_mm=thresholds.heavy_rain_mm)
    rain_level = rainfall_risk(summary, thresholds)
    return ErosionAssessment(
        elevation_m=terrain.elevation_m,
        slope_pct=slope,
        terrain_erosion_risk=terrain_level,
        rainfall=summary,
        rainfall_erosion_risk=rain_level,
        combined_erosion_risk=combined_risk(terrain_level, rain_level),
    )
