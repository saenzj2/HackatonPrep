"""Normalized domain types. Units are always: °C, mm, pH, m³/m³ (volumetric soil moisture)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.errors import DomainInvariantError

MONTHS = 12
MAX_ROOT_DEPTH_M = 5.0  # sanity bound: deepest field-crop roots in FAO-56 Table 22 are ~2-3 m

# Crop traits are stored and scored as 0..1 (1 = most). The API shows them as words via
# level_for(). Placeholder cutoffs: the data uses 0, 0.33, 0.67 and 1.0, one per band.
Level = Literal["none", "low", "medium", "high"]
# Every 0..1 trait on CropProfile. Add new traits here so the API guard test covers them.
TRAIT_FIELDS = ("forage_value", "nutrition_density", "mycorrhizal_affinity", "nitrogen_demand")
LOW_BELOW = 0.5  # (0, 0.5) → low
MEDIUM_BELOW = 0.8  # [0.5, 0.8) → medium, [0.8, 1] → high


def level_for(score: float) -> Level:
    """Word for a 0..1 trait score: 0 → none, then low, medium, high (see the cutoffs above)."""
    if not 0 <= score <= 1:
        raise DomainInvariantError(f"Trait score must be in [0, 1], got {score}")
    if score == 0:
        return "none"
    if score < LOW_BELOW:
        return "low"
    if score < MEDIUM_BELOW:
        return "medium"
    return "high"


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
    root_depth_m: float  # typical maximum effective rooting depth (FAO-56 Table 22, upper value)
    is_cover_crop: bool  # commonly grown to cover and protect the soil between cash crops
    # Trait scores, 0..1 (see level_for)
    forage_value: float  # value of the crop or its residue as animal feed
    nutrition_density: float  # nutrient density of the edible part
    mycorrhizal_affinity: float  # 0 = non-host (e.g. Brassicaceae, Amaranthaceae)
    nitrogen_demand: float  # 1 = heavy feeder
    market_note: str  # one line of local market context, may be empty
    sources: tuple[str, ...]  # citations for this crop's values
    # EcoCrop: the crop doesn't tolerate poorly drained soil (all but rice here). Enables the
    # waterlogging check; False = no check.
    needs_good_drainage: bool = False
    verified: bool = False  # True once the tolerance ranges come from a cited source (EcoCrop)

    def __post_init__(self) -> None:
        if not 0 < self.root_depth_m <= MAX_ROOT_DEPTH_M:
            raise DomainInvariantError(
                f"{self.id}: root_depth_m must be in (0, {MAX_ROOT_DEPTH_M}], "
                f"got {self.root_depth_m}"
            )
        if any(not 0 <= getattr(self, name) <= 1 for name in TRAIT_FIELDS):
            raise DomainInvariantError(f"{self.id}: trait scores must be in [0, 1]")
        if not self.sources:
            raise DomainInvariantError(f"{self.id}: every crop needs at least one source")


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
class MonthlySoilWater:
    """Root-zone soil water per calendar month, January first (NASA SMAP L4)."""

    moisture_m3m3: tuple[float, ...]  # volumetric water content
    wetness: tuple[float, ...]  # relative saturation, 0 = dry, 1 = saturated


@dataclass(frozen=True)
class SoilConditions:
    ph: float
    moisture_m3m3: float  # volumetric water content (m³/m³); the yearly mean when monthly is given
    # Mean moisture per calendar month (m³/m³), January first. When present, each season or
    # sowing month is scored on the mean of its own months instead of moisture_m3m3.
    moisture_monthly_m3m3: tuple[float, ...] | None = None

    def __post_init__(self) -> None:
        monthly = self.moisture_monthly_m3m3
        if monthly is not None and len(monthly) != MONTHS:
            raise DomainInvariantError("SoilConditions needs 12 monthly moisture values")
        wetness = self.wetness_monthly
        if wetness is not None and (
            len(wetness) != MONTHS or not all(0 <= w <= 1 for w in wetness)
        ):
            raise DomainInvariantError("SoilConditions needs 12 monthly wetness values in 0..1")

    # Mean relative saturation of the root zone per month (0 = dry, 1 = saturated), January first.
    # From the same model as the moisture, so it's comparable across soils. Drives waterlogging.
    wetness_monthly: tuple[float, ...] | None = None
    # USDA texture class of the topsoil (e.g. "clay"); only used to word the waterlogging warning.
    texture_class: str | None = None

    def wetness_for(self, months: tuple[int, ...]) -> float | None:
        """Mean relative saturation over the given months, or None without wetness data."""
        if self.wetness_monthly is None:
            return None
        return sum(self.wetness_monthly[m - 1] for m in months) / len(months)

    def moisture_for(self, months: tuple[int, ...]) -> float:
        """Mean moisture over the given months (1..12); the single value when there's no series."""
        if self.moisture_monthly_m3m3 is None:
            return self.moisture_m3m3
        return sum(self.moisture_monthly_m3m3[m - 1] for m in months) / len(months)


@dataclass(frozen=True)
class SoilLayer:
    """Soil properties at one depth. None = the source has no valid value there (never guessed)."""

    depth_cm: int
    ph: float | None  # pH in water (H2O)
    organic_carbon_g_kg: float | None
    clay_pct: float | None  # % of fine earth by weight (kg/kg)
    sand_pct: float | None
    silt_pct: float | None  # derived: 100 - clay - sand, see domain/soil.py
    bulk_density_kg_m3: float | None  # fine earth
    field_capacity_m3m3: float | None  # volumetric water content at 33 kPa suction
    texture_class: str | None  # USDA texture triangle class, e.g. "clay loam"


@dataclass(frozen=True)
class SoilProfile:
    """Soil properties at one location, one layer per depth, shallowest first."""

    lat: float
    lon: float
    layers: tuple[SoilLayer, ...]

    def __post_init__(self) -> None:
        depths = [layer.depth_cm for layer in self.layers]
        if not depths or depths != sorted(set(depths)):
            raise DomainInvariantError(
                "SoilProfile needs layers with unique depths, shallowest first"
            )


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
    waterlogging_factor: float = 1.0  # already applied to score; < 1 = some waterlogging risk
    waterlogging_warning: bool = False  # wet enough to warn the farmer (WATERLOGGING_NOTE)


@dataclass(frozen=True)
class RotationResult:
    sequence: tuple[CropSeasonFit, ...]
    score: float  # 0..1 after rotation adjustments
    breakdown: CategoryScores
    viable: bool
    benefits: tuple[str, ...] = field(default_factory=tuple)
    risks: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TerrainSample:
    """Elevation at a point and at its 4 neighbours (metres), for a local slope estimate.

    spacing_*_m is the horizontal distance from the centre to each neighbour on that axis.
    """

    elevation_m: float
    north_m: float
    south_m: float
    east_m: float
    west_m: float
    spacing_ns_m: float
    spacing_ew_m: float

    def __post_init__(self) -> None:
        if self.spacing_ns_m <= 0 or self.spacing_ew_m <= 0:
            raise DomainInvariantError(f"Terrain sample spacings must be > 0 m: {self}")
