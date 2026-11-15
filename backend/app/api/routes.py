"""All endpoints. Split into one module per resource once this file grows past ~150 lines."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from app import __version__, services
from app.api import schemas as s
from app.api.deps import Ctx
from app.api.errors import error_responses

router = APIRouter()

DATA_ERRORS = error_responses(422, 502, 503)  # routes that take input and fetch data


@router.get("/health", response_model=s.HealthResponse, responses=error_responses(), tags=["meta"])
def health(ctx: Ctx) -> s.HealthResponse:
    """Liveness check plus the active data mode and MVP region."""
    return s.HealthResponse(
        status="ok",
        version=__version__,
        data_mode=ctx.config.data_mode.value,
        region=ctx.region(),
    )


@router.get("/crops", response_model=s.CropsResponse, responses=error_responses(), tags=["crops"])
def list_crops(ctx: Ctx) -> s.CropsResponse:
    """Crops in the MVP scope, with their tolerance ranges."""
    return s.CropsResponse(crops=[services.crop_schema(c) for c in ctx.resolve_crops(None)])


@router.get("/conditions", response_model=s.Conditions, responses=DATA_ERRORS, tags=["conditions"])
def get_conditions(
    ctx: Ctx,
    lat: Annotated[float, Query(ge=-90, le=90, examples=[10.0])],
    lon: Annotated[float, Query(ge=-180, le=180, examples=[-84.2])],
) -> s.Conditions:
    """Monthly climate normals, per-season summary and soil at a point."""
    conditions, _, _ = services.get_conditions(ctx, lat, lon)
    return conditions


@router.get(
    "/planting-windows",
    response_model=s.PlantingWindowsResponse,
    responses=DATA_ERRORS,
    tags=["planting"],
)
def get_planting_windows(
    ctx: Ctx,
    lat: Annotated[float, Query(ge=-90, le=90, examples=[11.0])],
    lon: Annotated[float, Query(ge=-180, le=180, examples=[-84.6])],
    crops: Annotated[
        list[str] | None,
        Query(description="Crop ids from GET /crops, repeatable. Omit for the MVP crops."),
    ] = None,
) -> s.PlantingWindowsResponse:
    """Best sowing months per crop at a point: each month scored over the crop's cycle."""
    return services.planting_windows(ctx, lat, lon, crops)


@router.post(
    "/recommendations",
    response_model=s.RecommendationResponse,
    responses=DATA_ERRORS,
    tags=["recommendations"],
)
def create_recommendation(ctx: Ctx, req: s.RecommendationRequest) -> s.RecommendationResponse:
    """Rank crop rotations for a location given the farmer's priorities."""
    return services.recommend(ctx, req)


@router.post(
    "/plan-risk",
    response_model=s.PlanRiskResponse,
    responses=DATA_ERRORS,
    tags=["plan-risk"],
)
def create_plan_risk(ctx: Ctx, req: s.PlanRiskRequest) -> s.PlanRiskResponse:
    """Replay a crop + sowing date plan against past years of weather: when could it fail?"""
    return services.plan_risk(ctx, req)
