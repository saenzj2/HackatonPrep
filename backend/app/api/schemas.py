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


class SeasonSummary(Schema):
    name: str
    months: list[int]
    temperature_c: float
    rainfall_mm_per_month: float


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
    notes: list[str]


class RecommendationResponse(Schema):
    location: Location
    region: Region
    priorities: Priorities
    conditions: Conditions
    rotations: list[Rotation]
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
