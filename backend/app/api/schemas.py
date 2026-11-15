"""Request/response models. MUST match docs/api-contract.yaml (checked by tests/test_contract.py).

Change the contract first, agree on it with the frontend, then change these models.
Class names are the OpenAPI component names, so renaming a class is a contract change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

from app.domain.models import level_for
from app.errors import DomainInvariantError, ErrorCode


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


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
    explanation: str
    is_current: bool = Field(description="True if this is the farmer's current_rotation")
    score_delta_vs_current: float | None = Field(
        description="score minus the current rotation's score; null without current_rotation"
    )
    benefits: list[str] = Field(description="Why this rotation helps (soil, pests, fit)")
    risks: list[str] = Field(description="What could go wrong; check locally before acting")
    data_gaps: list[str] = Field(description="Missing or approximate data behind this result")
    evidence: list[str] = Field(description="The data values the score is based on, with sources")
    notes: list[str] = Field(description="Deprecated: benefits + risks. Use those instead.")


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
    dry_month_note: str | None = Field(
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
    fixed_limits: list[str] = Field(
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
