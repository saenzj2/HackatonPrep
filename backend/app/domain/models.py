"""Normalized domain types. Units are always: °C, mm, pH, m³/m³ (volumetric soil moisture)."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.errors import DomainInvariantError

MONTHS = 12


@dataclass(frozen=True)
class Range:
    """EcoCrop-style tolerance range: outside [abs_min, abs_max] the crop fails,
    inside [opt_min, opt_max] it is optimal."""

    abs_min: float
    opt_min: float
    opt_max: float
    abs_max: float

    def __post_init__(self) -> None:
        if not (self.abs_min <= self.opt_min <= self.opt_max <= self.abs_max):
            raise DomainInvariantError(
                f"Range must satisfy abs_min <= opt_min <= opt_max <= abs_max: {self}"
            )


@dataclass(frozen=True)
class CropProfile:
    id: str
    name: str
    scientific_name: str
    family: str
    is_legume: bool
    cycle_days: int
    temperature_c: Range
    rainfall_mm: Range  # total rainfall over the crop cycle
    soil_ph: Range
    verified: bool = False  # True once values were checked against the FAO EcoCrop source


@dataclass(frozen=True)
class MonthlyClimate:
    """Long-term monthly normals, index 0 = January."""

    temperature_c: tuple[float, ...]  # mean air temperature at 2 m
    rainfall_mm: tuple[float, ...]  # total rainfall in the month
    temperature_max_c: tuple[float, ...]  # mean of the daily maximum temperature at 2 m
    temperature_min_c: tuple[float, ...]  # mean of the daily minimum temperature at 2 m

    def __post_init__(self) -> None:
        series = (
            self.temperature_c,
            self.rainfall_mm,
            self.temperature_max_c,
            self.temperature_min_c,
        )
        if any(len(v) != MONTHS for v in series):
            raise DomainInvariantError("MonthlyClimate needs 12 values per variable")


@dataclass(frozen=True)
class SoilConditions:
    ph: float
    moisture_m3m3: float  # volumetric water content of the surface layer


@dataclass(frozen=True)
class Season:
    name: str
    months: tuple[int, ...]  # 1..12


@dataclass(frozen=True)
class SeasonClimate:
    season: Season
    temperature_c: float  # mean over the season's months
    rainfall_mm_per_month: float  # mean monthly total over the season's months
    temperature_max_c: float  # mean daily maximum over the season's months (heat stress)
    temperature_min_c: float  # mean daily minimum of the season's coldest month (frost risk)


@dataclass(frozen=True)
class Weights:
    water: float
    soil: float
    climate: float

    def normalized(self) -> Weights:
        total = self.water + self.soil + self.climate
        if total <= 0:
            raise DomainInvariantError("At least one priority weight must be > 0")
        return Weights(self.water / total, self.soil / total, self.climate / total)


@dataclass(frozen=True)
class CategoryScores:
    climate: float | None
    water: float | None
    soil: float | None


@dataclass(frozen=True)
class CropSeasonFit:
    crop: CropProfile
    season: Season
    variable_scores: dict[str, float]
    categories: CategoryScores
    score: float  # 0..1
    risks: tuple[str, ...] = ()  # limits exceeded, partial stress, cycle too long


@dataclass(frozen=True)
class RotationResult:
    sequence: tuple[CropSeasonFit, ...]
    score: float  # 0..1 after rotation adjustments
    breakdown: CategoryScores
    viable: bool
    benefits: tuple[str, ...] = field(default_factory=tuple)
    risks: tuple[str, ...] = field(default_factory=tuple)
