"""Orchestration: fetch from integrations → run domain logic → build API responses.

The only module that knows about all three layers (api schemas, integrations, domain).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import overload

from app.api import schemas as s
from app.domain.models import (
    CropProfile,
    MonthlyClimate,
    Range,
    Season,
    SoilConditions,
    Weights,
)
from app.domain.ranking import explain, rank_rotations
from app.domain.suitability import season_climate
from app.errors import InvalidPrioritiesError, OutOfRegionError, UnknownCropError
from app.integrations import Sources
from app.settings import MvpConfig

METHOD_VERSION = "suitability-v0"
SCORE_DECIMALS = 4  # the domain keeps full precision; we round only what goes in the response


@overload
def _score(x: float) -> float: ...
@overload
def _score(x: None) -> None: ...
def _score(x: float | None) -> float | None:
    return None if x is None else round(x, SCORE_DECIMALS)


@dataclass(frozen=True)
class AppContext:
    config: MvpConfig
    sources: Sources

    @property
    def seasons(self) -> list[Season]:
        return [Season(name=x.name, months=tuple(x.months)) for x in self.config.seasons]

    def region(self) -> s.Region:
        return s.Region(name=self.config.region.name, bbox=list(self.config.region.bbox))

    def check_location(self, lat: float, lon: float) -> None:
        if not self.config.region.contains(lat, lon):
            raise OutOfRegionError(
                f"Location ({lat}, {lon}) is outside the MVP region '{self.config.region.name}'",
                details={"lat": lat, "lon": lon, "bbox": list(self.config.region.bbox)},
            )

    def resolve_crops(self, ids: list[str] | None) -> list[CropProfile]:
        catalog = self.sources.crops.all()
        ids = self.config.crops if ids is None else ids
        unknown = [c for c in ids if c not in catalog]
        if unknown:
            raise UnknownCropError(
                f"Unknown crop ids: {', '.join(unknown)}",
                details={"unknown": unknown, "available": sorted(catalog)},
            )
        return [catalog[c] for c in dict.fromkeys(ids)]


def _range(r: Range) -> s.ToleranceRange:
    return s.ToleranceRange(
        abs_min=r.abs_min, opt_min=r.opt_min, opt_max=r.opt_max, abs_max=r.abs_max
    )


def crop_schema(c: CropProfile) -> s.Crop:
    return s.Crop(
        id=c.id,
        name=c.name,
        scientific_name=c.scientific_name,
        family=c.family,
        is_legume=c.is_legume,
        cycle_days=c.cycle_days,
        temperature_c=_range(c.temperature_c),
        rainfall_mm=_range(c.rainfall_mm),
        soil_ph=_range(c.soil_ph),
        verified=c.verified,
    )


def get_conditions(
    ctx: AppContext, lat: float, lon: float
) -> tuple[s.Conditions, MonthlyClimate, SoilConditions]:
    """Returns (schema, climate, soil) so recommendations can reuse the fetched data."""
    ctx.check_location(lat, lon)
    climate = ctx.sources.climate.monthly_climate(lat, lon)
    soil = ctx.sources.soil.soil(lat, lon)
    schema = s.Conditions(
        location=s.Location(lat=lat, lon=lon),
        monthly=[
            s.MonthClimate(month=i + 1, temperature_c=t, rainfall_mm=r)
            for i, (t, r) in enumerate(zip(climate.temperature_c, climate.rainfall_mm, strict=True))
        ],
        seasons=[
            s.SeasonSummary(
                name=sc.season.name,
                months=list(sc.season.months),
                temperature_c=round(sc.temperature_c, 2),
                rainfall_mm_per_month=round(sc.rainfall_mm_per_month, 1),
            )
            for sc in (season_climate(climate, season) for season in ctx.seasons)
        ],
        soil=s.Soil(ph=soil.ph, moisture_m3m3=soil.moisture_m3m3),
        data_sources=s.DataSources(**ctx.sources.names()),
    )
    return schema, climate, soil


def recommend(ctx: AppContext, req: s.RecommendationRequest) -> s.RecommendationResponse:
    crops = ctx.resolve_crops(req.crops)
    p = req.priorities or s.Priorities(**ctx.config.priority_weights.model_dump())
    if p.water + p.soil + p.climate <= 0:
        raise InvalidPrioritiesError(
            "At least one priority (water, soil, climate) must be greater than 0",
            details={"priorities": p.model_dump()},
        )
    weights = Weights(water=p.water, soil=p.soil, climate=p.climate).normalized()
    conditions, climate, soil = get_conditions(ctx, req.lat, req.lon)
    results = rank_rotations(
        crops=crops,
        seasons=ctx.seasons,
        climate=climate,
        soil=soil,
        weights=weights,
        variables=ctx.config.variables,
        top_n=req.top_n or ctx.config.top_n,
    )
    return s.RecommendationResponse(
        location=s.Location(lat=req.lat, lon=req.lon),
        region=ctx.region(),
        priorities=s.Priorities(
            water=round(weights.water, 4),
            soil=round(weights.soil, 4),
            climate=round(weights.climate, 4),
        ),
        conditions=conditions,
        rotations=[
            s.Rotation(
                rank=i + 1,
                sequence=[
                    s.RotationStep(
                        season=f.season.name,
                        months=list(f.season.months),
                        crop_id=f.crop.id,
                        crop_name=f.crop.name,
                        score=_score(f.score),
                        variable_scores={k: _score(v) for k, v in f.variable_scores.items()},
                    )
                    for f in r.sequence
                ],
                score=_score(r.score),
                viable=r.viable,
                breakdown=s.CategoryBreakdown(
                    climate=_score(r.breakdown.climate),
                    water=_score(r.breakdown.water),
                    soil=_score(r.breakdown.soil),
                ),
                explanation=explain(r),
                notes=list(r.notes),
            )
            for i, r in enumerate(results)
        ],
        method_version=METHOD_VERSION,
        generated_at=datetime.now(UTC),
    )
