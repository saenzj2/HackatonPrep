"""Request/response models. MUST match docs/api-contract.yaml (checked by tests/test_contract.py).

Change the contract first, agree on it with the frontend, then change these models.
Class names are the OpenAPI component names, so renaming a class is a contract change.
"""

from __future__ import annotations

import datetime as dt
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.domain.models import level_for
from app.errors import DomainInvariantError, ErrorCode


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LocalizedText(Schema):
    """Farmer-facing text in English and Spanish (Costa Rica). Show the one the user picked."""

    en: str
    es: str


class TraitValue(Schema):
    """A crop trait as a word for display plus its 0..1 score (e.g. for a hover)."""

    level: Literal["none", "low", "medium", "high"] = Field(description="Word for the score")
    score: float = Field(ge=0, le=1, description="0..1, 1 = most")

    @model_validator(mode="after")
    def _level_matches_score(self) -> TraitValue:
        # Deliberately not a ValueError (422): a mismatch is a backend bug, so it surfaces as a 500.
        if self.level != level_for(self.score):
            raise DomainInvariantError(
                f"Trait level '{self.level}' doesn't match score {self.score}; pass the score only"
            )
        return self


def _trait_from_score(value: object) -> object:
    """0..1 score → {level, score}. Anything else goes to normal TraitValue validation."""
    if isinstance(value, int | float) and not isinstance(value, bool):
        return {"level": level_for(value), "score": value}
    return value


# Crop traits in ANY response use this type (docs/crop-schema.md). Give it the domain's 0..1 score;
# the response shows {"level": word, "score": number}. tests/test_trait_levels.py enforces its use.
Trait = Annotated[TraitValue, BeforeValidator(_trait_from_score)]


class Location(Schema):
    """One representative point (decimal degrees). Values are for it, never an area average."""

    lat: float = Field(ge=-90, le=90, examples=[10.0])
    lon: float = Field(ge=-180, le=180, examples=[-84.2])


class Region(Schema):
    name: str
    bbox: list[float] = Field(description="[min_lon, min_lat, max_lon, max_lat]")


class HealthResponse(Schema):
    status: str
    version: str
    data_mode: str
    region: Region


class ToleranceRange(Schema):
    abs_min: float
    opt_min: float
    opt_max: float
    abs_max: float


class Crop(Schema):
    id: str
    name: str
    name_es: str = Field(description="Name in Spanish (Costa Rica)")
    scientific_name: str
    family: str
    is_legume: bool
    cycle_days: int
    temperature_c: ToleranceRange
    rainfall_mm: ToleranceRange = Field(description="Total rainfall over the crop cycle")
    soil_ph: ToleranceRange
    root_depth_m: float = Field(description="Typical maximum effective rooting depth, m")
    is_cover_crop: bool = Field(description="Commonly grown to cover and protect the soil")
    needs_good_drainage: bool = Field(
        description="EcoCrop: does not tolerate poorly drained soil (checked for waterlogging)"
    )
    forage_value: Trait = Field(description="Value of the crop or its residue as animal feed")
    nutrition_density: Trait = Field(description="Nutrient density of the edible part")
    mycorrhizal_affinity: Trait = Field(
        description="How much the crop hosts and benefits from mycorrhizal fungi; none = non-host"
    )
    nitrogen_demand: Trait = Field(description="Nitrogen need; high = heavy feeder")
    market_note: str = Field(description="One line of local market context; may be empty")
    sources: list[str] = Field(description="Citations for this crop's values")
    verified: bool = Field(description="False while values are still approximate")


class CropsResponse(Schema):
    crops: list[Crop]


class MonthClimate(Schema):
    month: int = Field(ge=1, le=12)
    temperature_c: float
    rainfall_mm: float
    temperature_max_c: float = Field(description="Mean of the daily maximum temperature, °C")
    temperature_min_c: float = Field(description="Mean of the daily minimum temperature, °C")


class SeasonSummary(Schema):
    name: str
    months: list[int]
    temperature_c: float
    rainfall_mm_per_month: float
    temperature_max_c: float = Field(
        description="Mean daily maximum temperature over the season, °C (heat stress)"
    )
    temperature_min_c: float = Field(
        description="Mean daily minimum of the season's coldest month, °C (frost risk)"
    )


class Soil(Schema):
    ph: float
    moisture_m3m3: float = Field(description="Yearly mean root-zone moisture, m³/m³")
    moisture_monthly_m3m3: list[float] | None = Field(
        description="Mean root-zone moisture per month (m³/m³), January first; null if unknown"
    )
    texture_class: str | None = Field(
        description="USDA texture class of the topsoil (OpenLandMap), e.g. clay; null if unknown"
    )
    wetness_monthly: list[float] | None = Field(
        description="Mean root-zone relative saturation per month (0 dry .. 1 saturated), January "
        "first; drives the waterlogging check. Null if unknown"
    )


class DataSources(Schema):
    climate: str
    soil: str
    crops: str


class Conditions(Schema):
    location: Location
    monthly: list[MonthClimate]
    seasons: list[SeasonSummary]
    soil: Soil
    data_sources: DataSources


class Priorities(Schema):
    water: float = Field(ge=0, examples=[0.4])
    soil: float = Field(ge=0, examples=[0.3])
    climate: float = Field(ge=0, examples=[0.3])


# Shared field descriptions (#41): the API takes one point and never substitutes crops.
POINT_NOTE = (
    "of one representative point. For a selected area, send one explicitly chosen point; "
    "results are for that point, never an area or polygon average."
)
UNSUPPORTED_CROP_NOTE = "Ids not in GET /crops fail with unknown_crop; they are never substituted."


class RecommendationRequest(Schema):
    lat: float = Field(ge=-90, le=90, examples=[10.0], description=f"Latitude {POINT_NOTE}")
    lon: float = Field(ge=-180, le=180, examples=[-84.2], description=f"Longitude {POINT_NOTE}")
    crops: list[str] | None = Field(
        default=None,
        min_length=1,
        description=(
            "Crop ids from GET /crops. Omit for the MVP crops; an empty list is invalid. "
            + UNSUPPORTED_CROP_NOTE
        ),
    )
    priorities: Priorities | None = Field(
        default=None, description="Relative importance; normalized to sum 1. Default: MVP weights."
    )
    top_n: int | None = Field(default=None, ge=1, le=50)
    current_rotation: list[str] | None = Field(
        default=None,
        description=(
            "The farmer's current rotation: crop ids from GET /crops, one per season, in the "
            "order of conditions.seasons. Scored as the baseline the other rotations compare to. "
            "Omit when there is no current crop: no baseline, so current_rotation and "
            "score_delta_vs_current are null. " + UNSUPPORTED_CROP_NOTE
        ),
        examples=[["maize", "maize"]],
    )


class CategoryBreakdown(Schema):
    climate: float | None
    water: float | None
    soil: float | None


class RotationStep(Schema):
    season: str
    months: list[int]
    crop_id: str
    crop_name: str
    score: float
    variable_scores: dict[str, float]


class Rotation(Schema):
    rank: int
    sequence: list[RotationStep]
    score: float = Field(ge=0, le=1)
    viable: bool
    breakdown: CategoryBreakdown
    explanation: LocalizedText
    is_current: bool = Field(description="True if this is the farmer's current_rotation")
    score_delta_vs_current: float | None = Field(
        description="score minus the current rotation's score; null without current_rotation"
    )
    benefits: list[LocalizedText] = Field(description="Why this rotation helps (soil, pests, fit)")
    risks: list[LocalizedText] = Field(
        description="What could go wrong; check locally before acting"
    )
    data_gaps: list[LocalizedText] = Field(
        description="Missing or approximate data behind this result"
    )
    evidence: list[LocalizedText] = Field(
        description="The data values the score is based on, with sources"
    )
    notes: list[LocalizedText] = Field(
        description="Deprecated: benefits + risks. Use those instead."
    )


class RecommendationResponse(Schema):
    location: Location
    region: Region
    priorities: Priorities
    conditions: Conditions
    rotations: list[Rotation]
    current_rotation: Rotation | None = Field(
        description=(
            "The farmer's rotation scored the same way; rank is its position among all "
            "combinations (can be greater than top_n). Null without current_rotation."
        )
    )
    method_version: str
    generated_at: datetime


class SowingMonth(Schema):
    sowing_month: int = Field(ge=1, le=12)
    months_in_field: list[int] = Field(
        description="Months the crop spends in the field when sown this month (wraps the year)"
    )
    score: float = Field(ge=0, le=1, description="Same scoring as rotations, 1 = ideal")
    is_good: bool = Field(
        description="Score on the month-varying variables >= 0.8 and none of them below 0.5 "
        "(soil pH is the same every month: see fixed_limits). Waterlogging never makes a month "
        "not good: see waterlogging_risk"
    )
    dry_month_note: LocalizedText | None = Field(
        description="Why this sowing month fails the dry-month check (a month in the field, "
        "harvest excluded, gets too little rain to establish and grow); null when it passes"
    )
    waterlogging_risk: bool = Field(
        description="The root zone is wet enough to warn about waterlogging for this crop (needs "
        "good drainage); the score already includes a small penalty (at most -15 %)"
    )
    limiting_factor: str | None = Field(
        description="Lowest-scoring variable (e.g. rainfall) when it is below 1, else null"
    )
    variable_scores: dict[str, float]


class PlantingWindow(Schema):
    first_month: int = Field(ge=1, le=12, description="Can wrap: first 11, last 1 = Nov to Jan")
    last_month: int = Field(ge=1, le=12)
    best_month: int = Field(ge=1, le=12)
    best_score: float = Field(ge=0, le=1)


class CropPlanting(Schema):
    crop_id: str
    crop_name: str
    cycle_days: int
    sowing_months: list[SowingMonth] = Field(description="Always 12, January first")
    fixed_limits: list[LocalizedText] = Field(
        description="Factors that are the same in every month (soil pH) and limit this crop here"
    )
    windows: list[PlantingWindow] = Field(
        description="Consecutive good sowing months; may be empty"
    )


class PlantingWindowsResponse(Schema):
    location: Location
    crops: list[CropPlanting] = Field(
        description="One per requested crop id (duplicates ignored), in request order"
    )
    data_sources: DataSources


# ---------------------------------------------------------------- daily weather, erosion, soil

POWER_DAILY_FIRST_DAY = dt.date(1981, 1, 1)  # NASA POWER daily data starts here
MAX_PERIOD_DAYS = 366  # one leap year; keeps live responses fast and payloads small
# NASA POWER publishes daily data late (3 days on 2026-11-15; longer at times). A period inside the
# delay would come back empty and fail as a 502, so `end` must be at least this many days ago.
# Margin chosen in the PR #94 review (docs/decisions.md).
POWER_DAILY_DELAY_DAYS = 30
RiskLevel = Literal["low", "medium", "high"]


class PointPeriodQuery(Schema):
    """Query parameters of GET /weather/daily and GET /erosion: one point and a date range.

    Never a response component: FastAPI turns it into the four query parameters. Unknown query
    parameters are ignored, like on every other GET endpoint (a cache-busting `_=` or a shared
    `lang` must not fail), unlike request bodies, which reject unknown fields.
    """

    model_config = ConfigDict(extra="ignore")

    lat: float = Field(ge=-90, le=90, examples=[9.93])
    lon: float = Field(ge=-180, le=180, examples=[-84.08])
    start: dt.date = Field(description="First day, YYYY-MM-DD (inclusive)", examples=["2026-01-01"])
    end: dt.date = Field(
        description="Last day, YYYY-MM-DD (inclusive). At most 366 days from start, and at least "
        "30 days before today: NASA POWER publishes daily data late",
        examples=["2026-01-31"],
    )

    @model_validator(mode="after")
    def _check_period(self) -> PointPeriodQuery:
        # ValueError here becomes the standard 422 validation_failed (docs/errors.md, rule 1).
        if self.start > self.end:
            raise ValueError("start must be on or before end")
        if (self.end - self.start).days + 1 > MAX_PERIOD_DAYS:
            raise ValueError(f"the period can be at most {MAX_PERIOD_DAYS} days")
        if self.start < POWER_DAILY_FIRST_DAY:
            raise ValueError(f"start must be on or after {POWER_DAILY_FIRST_DAY.isoformat()}")
        latest_end = datetime.now(dt.UTC).date() - dt.timedelta(days=POWER_DAILY_DELAY_DAYS)
        if self.end > latest_end:
            raise ValueError(
                f"end must be on or before {latest_end.isoformat()}: NASA POWER publishes "
                f"daily data with a delay, so the last {POWER_DAILY_DELAY_DAYS} days are not "
                "available yet"
            )
        return self


class DailyWeather(Schema):
    date: dt.date
    temperature_c: float | None = Field(
        description="Daily mean air temperature at 2 m (POWER T2M), °C; null if missing"
    )
    temperature_max_c: float | None = Field(
        description="Daily maximum air temperature at 2 m (POWER T2M_MAX), °C; null if missing "
        "or the source has no extremes (mock)"
    )
    temperature_min_c: float | None = Field(
        description="Daily minimum air temperature at 2 m (POWER T2M_MIN), °C; null if missing "
        "or the source has no extremes (mock)"
    )
    rainfall_mm: float | None = Field(
        description="Daily precipitation (POWER PRECTOTCORR), mm/day; null if missing"
    )


class DailyWeatherResponse(Schema):
    location: Location
    start: dt.date
    end: dt.date
    source: str = Field(description="Data source: nasa_power, or mock in mock mode")
    days: list[DailyWeather] = Field(description="One per day from start to end, oldest first")


class ErosionDataSources(Schema):
    terrain: str = Field(description="Elevation source: opentopography (SRTM GL1), or mock")
    weather: str = Field(description="Daily rainfall source: nasa_power, or mock")


class ErosionRiskResponse(Schema):
    location: Location
    start: dt.date
    end: dt.date
    elevation_m: int = Field(description="SRTM GL1 elevation, m above the EGM96 geoid")
    slope_pct: float = Field(ge=0, description="Local slope over ~30 m, %")
    terrain_erosion_risk: int = Field(
        ge=0, le=2, description="Slope only: 0 below 5 %, 1 from 5 to 15 %, 2 above 15 %"
    )
    terrain_erosion_level: RiskLevel = Field(description="terrain_erosion_risk as a word")
    total_rainfall_mm: float = Field(ge=0, description="Rainfall over the period, mm")
    avg_daily_rainfall_mm: float = Field(ge=0, description="Mean over days with data, mm/day")
    heavy_rain_days: int = Field(ge=0, description="Days with 30 mm or more")
    max_daily_rainfall_mm: float = Field(
        ge=0, description="Wettest day, mm. Reported only, not scored (grows with period length)"
    )
    combined_erosion_risk: int = Field(
        ge=0,
        le=2,
        description="Slope plus rain: high rain raises the terrain risk one step; never below "
        "terrain_erosion_risk",
    )
    combined_erosion_level: RiskLevel = Field(description="combined_erosion_risk as a word")
    data_sources: ErosionDataSources


class SoilProfileLayer(Schema):
    """Soil at one depth. null = no valid value for this pixel and depth, never guessed."""

    depth_cm: int = Field(ge=0, description="Depth below the surface, cm")
    ph: float | None = Field(description="pH in water (1:1 soil:water)")
    organic_carbon_g_kg: float | None = Field(
        description="Organic carbon, g/kg (stored in steps of 5 g/kg)"
    )
    clay_pct: float | None = Field(description="Clay, % of fine earth by weight")
    sand_pct: float | None = Field(description="Sand, % of fine earth by weight")
    silt_pct: float | None = Field(
        description="100 - clay - sand, %; null if either is missing or they add up to over 100"
    )
    bulk_density_kg_m3: float | None = Field(description="Bulk density of the fine earth, kg/m³")
    field_capacity_m3m3: float | None = Field(
        description="Volumetric water content at 33 kPa (field capacity), m³/m³"
    )
    texture_class: str | None = Field(description="USDA texture class, e.g. clay loam")


class SoilProfileResponse(Schema):
    location: Location
    source: str = Field(description="OpenLandMap, or mock in mock mode")
    attribution: str = Field(description="Credit line required by the CC-BY-SA 4.0 license")
    resolution_m: int = Field(description="Nominal pixel size of the maps, m")
    layers: list[SoilProfileLayer] = Field(description="0, 10 and 30 cm, shallowest first")


class ErrorBody(Schema):
    code: ErrorCode = Field(description="Stable machine-readable code. Switch on this.")
    message: str = Field(description="Plain-English explanation, safe to show to users")
    details: dict[str, Any] = Field(
        default_factory=dict, description="Machine-readable context; keys depend on the code"
    )
    request_id: str = Field(description="Same as the X-Request-ID header; quote it in bug reports")


class ErrorResponse(Schema):
    """Envelope for EVERY error response (4xx and 5xx). See backend/docs/errors.md."""

    error: ErrorBody
