"""Orchestration: fetch from integrations → run domain logic → build API responses.

The only module that knows about all three layers (api schemas, integrations, domain).
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import TypedDict, overload

from app.api import schemas as s
from app.domain.erosion import (
    DEFAULT_RAINFALL_THRESHOLDS,
    RainfallThresholds,
    assess_erosion,
)
from app.domain.models import (
    CropProfile,
    MonthlyClimate,
    Range,
    RotationResult,
    Season,
    SoilConditions,
    Weights,
)
from app.domain.ranking import explain, rank_rotations
from app.domain.suitability import cycle_rainfall_mm, season_climate
from app.errors import (
    InvalidPrioritiesError,
    InvalidRotationError,
    OutOfRegionError,
    SourceDataError,
    UnknownCropError,
)
from app.integrations import Sources
from app.integrations.base import DailyWeatherSource, TerrainSource
from app.settings import MvpConfig

METHOD_VERSION = "suitability-v1"
SOURCE_LABELS = {"nasa_power": "NASA POWER monthly normals", "mock": "mock data"}
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
        root_depth_m=c.root_depth_m,
        is_cover_crop=c.is_cover_crop,
        forage_value=c.forage_value,  # 0..1 score; Trait adds the word
        nutrition_density=c.nutrition_density,  # 0..1 score; Trait adds the word
        mycorrhizal_affinity=c.mycorrhizal_affinity,  # 0..1 score; Trait adds the word
        nitrogen_demand=c.nitrogen_demand,  # 0..1 score; Trait adds the word
        market_note=c.market_note,
        sources=list(c.sources),
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
            s.MonthClimate(
                month=i + 1,
                temperature_c=t,
                rainfall_mm=r,
                temperature_max_c=hi,
                temperature_min_c=lo,
            )
            for i, (t, r, hi, lo) in enumerate(
                zip(
                    climate.temperature_c,
                    climate.rainfall_mm,
                    climate.temperature_max_c,
                    climate.temperature_min_c,
                    strict=True,
                )
            )
        ],
        seasons=[
            s.SeasonSummary(
                name=sc.season.name,
                months=list(sc.season.months),
                temperature_c=round(sc.temperature_c, 2),
                rainfall_mm_per_month=round(sc.rainfall_mm_per_month, 1),
                temperature_max_c=round(sc.temperature_max_c, 2),
                temperature_min_c=round(sc.temperature_min_c, 2),
            )
            for sc in (season_climate(climate, season) for season in ctx.seasons)
        ],
        soil=s.Soil(ph=soil.ph, moisture_m3m3=soil.moisture_m3m3),
        data_sources=s.DataSources(**ctx.sources.names()),
    )
    return schema, climate, soil


def _current_rotation(
    ctx: AppContext, ids: list[str] | None
) -> tuple[tuple[str, ...] | None, list[CropProfile]]:
    """Validate the farmer's rotation. Returns (crop ids per season, its crop profiles)."""
    if ids is None:
        return None, []
    seasons = [x.name for x in ctx.seasons]
    if len(ids) != len(seasons):
        raise InvalidRotationError(
            f"current_rotation needs one crop per season ({', '.join(seasons)}), got {len(ids)}",
            details={"expected_length": len(seasons), "seasons": seasons, "got": ids},
        )
    return tuple(ids), ctx.resolve_crops(ids)


def _crop_ids(r: RotationResult) -> tuple[str, ...]:
    return tuple(f.crop.id for f in r.sequence)


def _month_span(months: Sequence[int]) -> str:
    return f"{calendar.month_abbr[months[0]]}–{calendar.month_abbr[months[-1]]}"


def _evidence(
    r: RotationResult, climate: MonthlyClimate, soil: SoilConditions, sources: dict[str, str]
) -> list[str]:
    """The data values behind the score, so a farmer or agronomist can check them."""
    climate_src = SOURCE_LABELS.get(sources["climate"], sources["climate"])
    soil_src = SOURCE_LABELS.get(sources["soil"], sources["soil"])
    lines: list[str] = []
    for f in r.sequence:
        sc = season_climate(climate, f.season)
        lines.append(
            f"{f.season.name} ({_month_span(f.season.months)}): mean {sc.temperature_c:.1f} °C, "
            f"average daily max {sc.temperature_max_c:.1f} °C, coldest-month daily min "
            f"{sc.temperature_min_c:.1f} °C, {sc.rainfall_mm_per_month:.0f} mm/month "
            f"({climate_src})"
        )
        rain = f.crop.rainfall_mm
        lines.append(
            f"{f.crop.name} in {f.season.name}: ~{cycle_rainfall_mm(sc, f.crop):.0f} mm over its "
            f"{f.crop.cycle_days}-day cycle (optimal {rain.opt_min:g} to {rain.opt_max:g} mm)"
        )
    lines.append(f"Soil: pH {soil.ph:.1f}, moisture {soil.moisture_m3m3:.2f} m³/m³ ({soil_src})")
    return list(dict.fromkeys(lines))


def _data_gaps(r: RotationResult, sources: dict[str, str], variables: Sequence[str]) -> list[str]:
    """What is missing or approximate behind this result. Shown so nobody over-trusts it."""
    gaps: list[str] = []
    if sources["climate"] == "mock":
        gaps.append("Climate values are mock data, not NASA POWER measurements")
    if sources["soil"] == "mock":
        gaps.append("Soil pH and moisture are mock values, not measured for this location")
    if "soil_moisture" in variables:
        gaps.append("Soil moisture uses one generic range for all crops")
    if "frost" in variables:
        gaps.append("Frost risk uses one generic threshold for all crops")
    for c in dict.fromkeys(f.crop for f in r.sequence):
        if not c.verified:
            gaps.append(f"{c.name} tolerance ranges are approximate (not yet verified)")
    return gaps


@dataclass(frozen=True)
class _RotationContext:
    """Everything a Rotation schema needs besides the rotation itself."""

    climate: MonthlyClimate
    soil: SoilConditions
    sources: dict[str, str]
    variables: Sequence[str]
    current: RotationResult | None


def _rotation_schema(r: RotationResult, rank: int, rc: _RotationContext) -> s.Rotation:
    is_current = rc.current is not None and _crop_ids(r) == _crop_ids(rc.current)
    return s.Rotation(
        rank=rank,
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
        is_current=is_current,
        score_delta_vs_current=(None if rc.current is None else _score(r.score - rc.current.score)),
        benefits=list(r.benefits),
        risks=list(r.risks),
        data_gaps=_data_gaps(r, rc.sources, rc.variables),
        evidence=_evidence(r, rc.climate, rc.soil, rc.sources),
        notes=[*r.benefits, *r.risks],
    )


def recommend(ctx: AppContext, req: s.RecommendationRequest) -> s.RecommendationResponse:
    crops = ctx.resolve_crops(req.crops)
    current_ids, current_crops = _current_rotation(ctx, req.current_rotation)
    # The farmer's crops join the candidates so the baseline is ranked with the alternatives.
    crops += [c for c in current_crops if c not in crops]
    p = req.priorities or s.Priorities(**ctx.config.priority_weights.model_dump())
    if p.water + p.soil + p.climate <= 0:
        raise InvalidPrioritiesError(
            "At least one priority (water, soil, climate) must be greater than 0",
            details={"priorities": p.model_dump()},
        )
    weights = Weights(water=p.water, soil=p.soil, climate=p.climate).normalized()
    conditions, climate, soil = get_conditions(ctx, req.lat, req.lon)
    ranked = rank_rotations(
        crops=crops,
        seasons=ctx.seasons,
        climate=climate,
        soil=soil,
        weights=weights,
        variables=ctx.config.variables,
        top_n=None,
    )
    current_rank = next((i for i, r in enumerate(ranked) if _crop_ids(r) == current_ids), None)
    rc = _RotationContext(
        climate=climate,
        soil=soil,
        sources=ctx.sources.names(),
        variables=ctx.config.variables,
        current=None if current_rank is None else ranked[current_rank],
    )
    top = ranked[: req.top_n or ctx.config.top_n]
    return s.RecommendationResponse(
        location=s.Location(lat=req.lat, lon=req.lon),
        region=ctx.region(),
        priorities=s.Priorities(
            water=round(weights.water, 4),
            soil=round(weights.soil, 4),
            climate=round(weights.climate, 4),
        ),
        conditions=conditions,
        rotations=[_rotation_schema(r, i + 1, rc) for i, r in enumerate(top)],
        current_rotation=(
            None
            if current_rank is None
            else _rotation_schema(ranked[current_rank], current_rank + 1, rc)
        ),
        method_version=METHOD_VERSION,
        generated_at=datetime.now(UTC),
    )


class ErosionRiskResult(TypedDict):
    """erosion_risk() output. Becomes a schema in app/api/schemas.py once an endpoint exists."""

    elevation_m: int  # SRTM GL1, m above the EGM96 geoid
    slope_pct: float
    terrain_erosion_risk: int  # 0 low, 1 medium, 2 high
    total_rainfall_mm: float
    avg_daily_rainfall_mm: float  # mm/day over the days with data
    heavy_rain_days: int  # days with >= HEAVY_RAIN_MM
    max_daily_rainfall_mm: float  # reported only, not scored
    combined_erosion_risk: int  # 0 low, 1 medium, 2 high; never below terrain_erosion_risk


def erosion_risk(
    *,
    terrain_source: TerrainSource,
    weather_source: DailyWeatherSource,
    lat: float,
    lon: float,
    start: date,
    end: date,
    thresholds: RainfallThresholds = DEFAULT_RAINFALL_THRESHOLDS,
) -> ErosionRiskResult:
    """Terrain (SRTM slope) and combined (slope + NASA POWER daily rain) erosion risk, 0 to 2.

    1. Slope: SRTM GL1 elevation at the point and its 4 neighbours one sample (~30 m) N/S/E/W,
       central differences with distances in metres. Terrain risk: < 5 % low (0),
       5-15 % medium (1), > 15 % high (2).
    2. Rainfall over start..end (inclusive), missing days skipped: total mm, average mm/day,
       heavy days (>= 30 mm) and the wettest day. Rainfall risk is the worse of two rates
       (thresholds in `RainfallThresholds`, overridable): average mm/day and heavy days per
       30 days, so a month and a year are judged on the same scale. The wettest day is reported
       but not scored, because it keeps growing with the period length.
    3. Combined: slope sets the base level, high rain raises it one step (flat land reaches
       medium at most), and it is never lower than the terrain risk:
           rainfall ->   low  medium  high
           flat (0)       0     0      1
           medium (1)     1     1      2
           steep (2)      2     2      2
       Medium rain never changes the result, on purpose (decisions.md).

    Returns the 8 fields of the erosion output, rounded for display. All thresholds are
    placeholders (docs/decisions.md). Not exposed over HTTP yet: that needs an api-contract.yaml
    change. API cost: 5 OpenTopography calls (free key: 50/day) the first time a location is seen,
    in any mode afterwards 0 (SRTM never changes, so cached points are reused even in live mode);
    1 POWER call per request in live mode (no key or quota).
    """
    terrain = terrain_source.terrain_sample(lat, lon)
    rain_mm = weather_source.daily_weather(lat=lat, lon=lon, start=start, end=end)["rainfall_mm"]
    if rain_mm.isna().all():
        # Temperature may exist while rainfall is missing for the whole period.
        raise SourceDataError(
            "NASA POWER has no daily rainfall for this point and period",
            details={"source": weather_source.name},
        )
    a = assess_erosion(terrain=terrain, daily_rainfall_mm=rain_mm.tolist(), thresholds=thresholds)
    return {
        "elevation_m": round(a.elevation_m),
        "slope_pct": round(a.slope_pct, 1),
        "terrain_erosion_risk": int(a.terrain_erosion_risk),
        "total_rainfall_mm": round(a.rainfall.total_mm, 1),
        "avg_daily_rainfall_mm": round(a.rainfall.avg_daily_mm, 2),
        "heavy_rain_days": a.rainfall.heavy_rain_days,
        "max_daily_rainfall_mm": round(a.rainfall.max_daily_mm, 1),
        "combined_erosion_risk": int(a.combined_erosion_risk),
    }
