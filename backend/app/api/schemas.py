"""Request/response models. MUST match docs/api-contract.yaml (checked by tests/test_contract.py).

Change the contract first, agree on it with the frontend, then change these models.
Class names are the OpenAPI component names, so renaming a class is a contract change.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.errors import ErrorCode


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Location(Schema):
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
    moisture_m3m3: float


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


class RecommendationRequest(Schema):
    lat: float = Field(ge=-90, le=90, examples=[10.0])
    lon: float = Field(ge=-180, le=180, examples=[-84.2])
    crops: list[str] | None = Field(
        default=None,
        min_length=1,
        description="Crop ids from GET /crops. Omit for the MVP crops; an empty list is invalid.",
    )
    priorities: Priorities | None = Field(
        default=None, description="Relative importance; normalized to sum 1. Default: MVP weights."
    )
    top_n: int | None = Field(default=None, ge=1, le=50)
    current_rotation: list[str] | None = Field(
        default=None,
        description=(
            "The farmer's current rotation: crop ids from GET /crops, one per season, in the "
            "order of conditions.seasons. Scored as the baseline the other rotations compare to."
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
