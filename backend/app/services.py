"""Orchestration: fetch from integrations → run domain logic → build API responses.

The only module that knows about all three layers (api schemas, integrations, domain).
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Any, Literal, TypedDict, overload

import pandas as pd

from app.api import schemas as s
from app.domain.enso import (
    ENSO_UNAVAILABLE,
    EnsoIndex,
    disagreement_note,
    enso_split,
    label_disagreements,
    latest_estimate_note,
    phase_of,
    year_phase,
)
from app.domain.erosion import (
    DEFAULT_RAINFALL_THRESHOLDS,
    ErosionRisk,
    RainfallThresholds,
    assess_erosion,
)
from app.domain.indicators import monthly_indicators
from app.domain.models import (
    CropProfile,
    MonthlyClimate,
    PerennialCropProfile,
    Range,
    RotationResult,
    Season,
    SoilConditions,
    SoilLayer,
    Weights,
)
from app.domain.perennials import (
    PerennialFit,
    dry_season_note,
    perennial_fit,
    year_climate,
)
from app.domain.perennials import rank as rank_perennials
from app.domain.perennials import summary as perennial_summary
from app.domain.plan_advice import (
    actions_for,
    day_month,
    find_alternatives,
    harvest_day,
    plan_summary,
    warm_nights_note,
)
from app.domain.plan_advice import explanation as plan_explanation
from app.domain.plan_risk import (
    FLOWERING_DRY_ALWAYS_FAIL_DAYS,
    DailyHistory,
    PlanRiskResult,
    stress_test,
)
from app.domain.planting_windows import SowingMonth, fixed_limits, sowing_calendar
from app.domain.planting_windows import planting_windows as find_planting_windows
from app.domain.ranking import crop_caveats, explain, rank_rotations
from app.domain.suitability import MARGINAL_SCORE, cycle_rainfall_mm, season_climate
from app.domain.text import Text, num, pct
from app.domain.text import month as text_month
from app.domain.text import month_span as text_month_span
from app.errors import (
    InvalidPrioritiesError,
    InvalidRotationError,
    OutOfRegionError,
    SourceDataError,
    SourceError,
    UnknownCropError,
)
from app.integrations import Sources, build_sources
from app.integrations.base import DailyWeatherSource, SoilProfileSource, TerrainSource
from app.integrations.measured_soil import SOURCE as MEASURED_SOIL_SOURCE
from app.settings import MvpConfig, get_config, get_env

log = logging.getLogger(__name__)

METHOD_VERSION = "suitability-v1"
SOURCE_LABELS = {
    "nasa_power": "NASA POWER monthly normals",
    "openlandmap+nasa_smap": "OpenLandMap pH, NASA SMAP moisture",
    "mock": "mock data",
}
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
        unknown = [c for c in dict.fromkeys(ids) if c not in catalog]  # once each, in request order
        if unknown:
            raise UnknownCropError(
                f"Unknown crop ids: {', '.join(unknown)}",
                details={"unknown": unknown, "available": sorted(catalog)},
            )
        return [catalog[c] for c in dict.fromkeys(ids)]

    def resolve_permanent_crops(self, ids: list[str] | None) -> list[PerennialCropProfile]:
        catalog = self.sources.perennials.all()
        ids = self.config.permanent_crops if ids is None else ids
        unknown = [c for c in dict.fromkeys(ids) if c not in catalog]
        if unknown:
            raise UnknownCropError(
                f"Unknown permanent crop ids: {', '.join(unknown)}",
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
        name_es=c.label.es,
        scientific_name=c.scientific_name,
        family=c.family,
        is_legume=c.is_legume,
        cycle_days=c.cycle_days,
        temperature_c=_range(c.temperature_c),
        rainfall_mm=_range(c.rainfall_mm),
        soil_ph=_range(c.soil_ph),
        root_depth_m=c.root_depth_m,
        is_cover_crop=c.is_cover_crop,
        needs_good_drainage=c.needs_good_drainage,
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
        soil=s.Soil(
            ph=soil.ph,
            moisture_m3m3=soil.moisture_m3m3,
            moisture_monthly_m3m3=None
            if soil.moisture_monthly_m3m3 is None
            else list(soil.moisture_monthly_m3m3),
            wetness_monthly=None if soil.wetness_monthly is None else list(soil.wetness_monthly),
            texture_class=soil.texture_class,
        ),
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


SOURCE_TEXT = {
    "nasa_power": Text("NASA POWER, long-term averages", "NASA POWER, promedios de largo plazo"),
    "mock": Text("simulated data", "datos simulados"),
}


def _source(name: str) -> Text:
    return SOURCE_TEXT.get(name, Text(name, name))


def _lt(text: Text) -> s.LocalizedText:
    return s.LocalizedText(en=text.en, es=text.es)


def _lt_or_none(text: Text | None) -> s.LocalizedText | None:
    return None if text is None else _lt(text)


def _evidence(
    r: RotationResult, climate: MonthlyClimate, soil: SoilConditions, sources: dict[str, str]
) -> list[Text]:
    """The data values behind the score, so a farmer or agronomist can check them."""
    src = _source(sources["climate"])
    lines: list[Text] = []
    for f in r.sequence:
        sc = season_climate(climate, f.season)
        span = text_month_span(f.season.months)
        t, hi, lo = (
            num(sc.temperature_c, 1),
            num(sc.temperature_max_c, 1),
            num(sc.temperature_min_c, 1),
        )
        rain_month = num(sc.rainfall_mm_per_month)
        lines.append(
            Text(
                f"{f.season.name} ({span.en}): average {t.en} °C, hottest hours ~{hi.en} °C, "
                f"coolest nights ~{lo.en} °C, ~{rain_month.en} mm of rain per month ({src.en})",
                f"{f.season.name} ({span.es}): promedio {t.es} °C, máximas ~{hi.es} °C, mínimas "
                f"~{lo.es} °C, ~{rain_month.es} mm de lluvia al mes ({src.es})",
            )
        )
        rain = f.crop.rainfall_mm
        cycle = num(cycle_rainfall_mm(sc, f.crop))
        lo_r, hi_r = num(rain.opt_min), num(rain.opt_max)
        a = f.crop.label
        lines.append(
            Text(
                f"{a.en} in {f.season.name}: ~{cycle.en} mm of rain over its "
                f"{f.crop.cycle_days}-day cycle (best {lo_r.en} to {hi_r.en} mm)",
                f"{a.es} en {f.season.name}: ~{cycle.es} mm de lluvia en su ciclo de "
                f"{f.crop.cycle_days} días (lo ideal es {lo_r.es} a {hi_r.es} mm)",
            )
        )
    lines.append(_soil_evidence(r, soil, sources["soil"]))
    return list(dict.fromkeys(lines))


def _soil_evidence(r: RotationResult, soil: SoilConditions, source: str) -> Text:
    """pH plus, when known, how saturated the root zone is in each season (the data behind a
    waterlogging warning). Scales and sources stated, no m³/m³."""
    ph = num(soil.ph, 1)
    if source != MEASURED_SOIL_SOURCE:
        src = _source(source)
        moist = num(soil.moisture_m3m3, 2)
        return Text(
            f"Soil: pH {ph.en}, moisture {moist.en} m³/m³ ({src.en})",
            f"Suelo: pH {ph.es}, humedad {moist.es} m³/m³ ({src.es})",
        )
    seasons = [
        (f.season.name, w)
        for f in r.sequence
        if (w := soil.wetness_for(f.season.months)) is not None
    ]
    seasons = list(dict.fromkeys(seasons))
    sat_en = " and ".join(f"{name} ({pct(w).en})" for name, w in seasons)
    sat_es = " y ".join(f"{name} ({pct(w).es})" for name, w in seasons)
    return Text(
        f"Soil: pH {ph.en} (OpenLandMap soil map, 250 m); root zone saturation in {sat_en} "
        "(NASA SMAP, ~9 km)",
        f"Suelo: pH {ph.es} (mapa de suelos OpenLandMap, 250 m); saturación del suelo en {sat_es} "
        "(NASA SMAP, ~9 km)",
    )


MEASURED_SOIL_GAPS = (
    Text(
        "Soil pH comes from the OpenLandMap soil map (250 m, 0-30 cm), not a soil test of your "
        "field",
        "El pH sale del mapa de suelos OpenLandMap (250 m, 0-30 cm), no de un análisis de suelo de "
        "su finca",
    ),
    Text(
        "Soil moisture comes from NASA SMAP (satellite + model), averaged over ~9 km and the years "
        "2020-2024, not measured in your field",
        "La humedad del suelo viene de NASA SMAP (satélite + modelo), promedio de un área de ~9 km "
        "y de los años 2020-2024; no se midió en su finca",
    ),
    Text(
        "The waterlogging warning uses how close to saturated the soil is over ~9 km; it can't see "
        "your field's own drainage (slope, ditches)",
        "El aviso de encharcamiento usa qué tan saturado está el suelo en un área de ~9 km; no ve "
        "el drenaje propio de su terreno (pendiente, zanjas)",
    ),
)
PLACEHOLDER_RULES_GAP = Text(
    "Scoring thresholds and rotation rule values are provisional, not yet reviewed by an "
    "agronomist",
    "Los límites de puntaje y las reglas de rotación son provisionales; aún no los revisa un "
    "agrónomo",
)


def _data_gaps(r: RotationResult, sources: dict[str, str], variables: Sequence[str]) -> list[Text]:
    """What is missing or approximate behind this result. Shown so nobody over-trusts it."""
    gaps: list[Text] = []
    if sources["climate"] == "mock":
        gaps.append(
            Text(
                "Climate values are simulated, not NASA POWER data",
                "Los datos de clima son simulados, no de NASA POWER",
            )
        )
    if sources["soil"] == "mock":
        gaps.append(
            Text(
                "Soil pH and moisture are simulated, not measured for this location",
                "El pH y la humedad del suelo son simulados, no medidos en este lugar",
            )
        )
    elif sources["soil"] == MEASURED_SOIL_SOURCE:
        gaps.extend(MEASURED_SOIL_GAPS)
    if "soil_moisture" in variables:
        gaps.append(
            Text(
                "The dry-soil limit is the same for all crops",
                "El límite de suelo seco es el mismo para todos los cultivos",
            )
        )
    if "frost" in variables:
        gaps.append(
            Text(
                "Frost risk uses the same limit for all crops",
                "El riesgo de helada usa el mismo límite para todos los cultivos",
            )
        )
    for c in dict.fromkeys(f.crop for f in r.sequence):
        if not c.verified:
            gaps.append(
                Text(
                    f"{c.label.en} tolerance ranges are approximate (not yet verified)",
                    f"Los rangos de tolerancia {c.of_the_es} son aproximados (aún sin verificar)",
                )
            )
    # True until an agronomist reviews them (docs/decisions.md), so data_gaps is never empty.
    gaps.append(PLACEHOLDER_RULES_GAP)
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
        explanation=_lt(explain(r)),
        is_current=is_current,
        score_delta_vs_current=(None if rc.current is None else _score(r.score - rc.current.score)),
        benefits=[_lt(t) for t in r.benefits],
        risks=[_lt(t) for t in (*r.risks, *crop_caveats(r))],
        data_gaps=[_lt(t) for t in _data_gaps(r, rc.sources, rc.variables)],
        evidence=[_lt(t) for t in _evidence(r, rc.climate, rc.soil, rc.sources)],
        notes=[_lt(t) for t in (*r.benefits, *r.risks, *crop_caveats(r))],
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
    """erosion_risk() output. GET /erosion returns it as ErosionRiskResponse (+ level words)."""

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
    placeholders (docs/decisions.md). Served over HTTP by GET /erosion (erosion_response).
    API cost: 5 OpenTopography calls (free key: 50/day) the first time a location is seen,
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


class MonthlyIndicatorsResult(TypedDict):
    """One row of field_indicators(). Becomes an api/schemas.py schema once an endpoint exists.

    `None` = no data for that variable in the month. heat_stress_days and frost_days come from true
    daily max / min (NASA POWER daily T2M_MAX / T2M_MIN); they are `None` when the source has no
    extrema (e.g. the mock source) or none for any day of the month.
    """

    year: int
    month: int  # 1..12
    days: int  # days of the month inside start..end
    temperature_days: int  # days with a mean temperature
    rainfall_days: int  # days with rainfall data
    extrema_days: int  # days with both daily max and min temperature
    mean_temperature_c: float | None  # mean of the daily means (T2M), 2 decimals
    total_rainfall_mm: float | None  # sum over rainfall_days only, 1 decimal
    dry_days: int | None  # rainfall < 1 mm
    longest_dry_spell_days: int | None  # consecutive dry days, cut at month edges
    extreme_rain_days: int | None  # rainfall >= 30 mm
    heat_stress_days: int | None  # daily max >= 35 °C (provisional generic threshold)
    frost_days: int | None  # daily min <= 0 °C


def _round(x: float | None, ndigits: int) -> float | None:
    return None if x is None else round(x, ndigits)


def field_indicators(
    *, weather_source: DailyWeatherSource, lat: float, lon: float, start: date, end: date
) -> list[MonthlyIndicatorsResult]:
    """Monthly indicator table for a field from its daily series, start..end inclusive.

    Uses `temperature_max_c` / `temperature_min_c` columns when the source returns them; without
    them, heat-stress and frost days stay None instead of being guessed from the daily mean.
    Thresholds, units and missing-day rules: docs/indicators.md. Not exposed over HTTP yet.
    """
    df = weather_source.daily_weather(lat=lat, lon=lon, start=start, end=end)
    has_extrema = {"temperature_max_c", "temperature_min_c"} <= set(df.columns)
    months = monthly_indicators(
        dates=[d.date() for d in df["date"]],
        temperature_c=df["temperature_c"].tolist(),
        rainfall_mm=df["rainfall_mm"].tolist(),
        temperature_max_c=df["temperature_max_c"].tolist() if has_extrema else None,
        temperature_min_c=df["temperature_min_c"].tolist() if has_extrema else None,
    )
    return [
        {
            "year": m.year,
            "month": m.month,
            "days": m.days,
            "temperature_days": m.temperature_days,
            "rainfall_days": m.rainfall_days,
            "extrema_days": m.extrema_days,
            "mean_temperature_c": _round(m.mean_temperature_c, 2),
            "total_rainfall_mm": _round(m.total_rainfall_mm, 1),
            "dry_days": m.dry_days,
            "longest_dry_spell_days": m.longest_dry_spell_days,
            "extreme_rain_days": m.extreme_rain_days,
            "heat_stress_days": m.heat_stress_days,
            "frost_days": m.frost_days,
        }
        for m in months
    ]


def _limiting_factor(variable_scores: dict[str, float]) -> str | None:
    if not variable_scores:
        return None
    name = min(variable_scores, key=lambda v: variable_scores[v])
    return name if variable_scores[name] < 1 else None


def _dry_month_note(crop: CropProfile, m: SowingMonth) -> Text | None:
    """Farmer note when a sowing month fails the dry-month check, else None."""
    dry = m.dry_month
    if dry is None or dry.score >= MARGINAL_SCORE:
        return None
    sown, driest, a = text_month(m.sowing_month), text_month(dry.month), crop.label
    al = a.lower()
    rain, need, least = num(dry.rainfall_mm), num(dry.pass_mm), num(dry.limit_mm)
    needs_en = (
        f"{al.en} needs about {need.en} mm a month to establish and grow (at least {least.en})"
    )
    needs_es = (
        f"{crop.the_es} necesita unos {need.es} mm al mes para establecerse y crecer "
        f"(mínimo {least.es})"
    )
    if dry.month == m.sowing_month:
        return Text(
            f"Too dry to establish {al.en} sown in {sown.en}: {sown.en} usually gets only "
            f"{rain.en} mm of rain, and {needs_en}",
            f"Muy seco para establecer {a.es.lower()} sembrado en {sown.es}: {sown.es} suele "
            f"tener solo {rain.es} mm de lluvia, y {needs_es}",
        )
    return Text(
        f"Sowing {al.en} in {sown.en} is risky: {driest.en} usually gets only {rain.en} mm of "
        f"rain, and {needs_en}",
        f"Sembrar {a.es.lower()} en {sown.es} es riesgoso: {driest.es} suele tener solo {rain.es} "
        f"mm de lluvia, y {needs_es}",
    )


def _fixed_limit_notes(
    crop: CropProfile, soil: SoilConditions, limits: dict[str, float]
) -> list[Text]:
    """Notes for the fixed factors (same every month) that limit this crop. The pH comes from a
    250 m map: say so and suggest a soil test, never an absolute verdict on the field."""
    notes = []
    if "soil_ph" in limits:
        r, a, ph = crop.soil_ph, crop.label, num(soil.ph, 1)
        al = a.lower()
        if limits["soil_ph"] == 0:
            lo, hi = num(r.abs_min, 1), num(r.abs_max, 1)
            notes.append(
                Text(
                    f"Soil pH {ph.en} (soil map, 250 m) is outside what {al.en} tolerates "
                    f"({lo.en}-{hi.en}). Confirm with a soil test; if it is right, {al.en} won't "
                    "do well here in any month without liming",
                    f"El pH del suelo {ph.es} (mapa de suelos, 250 m) está fuera de lo que tolera "
                    f"{crop.the_es} ({lo.es}-{hi.es}). Confírmelo con un análisis de suelo; si "
                    f"es correcto, {crop.the_es} no se daría bien en ningún mes sin encalar",
                )
            )
        else:
            lo, hi = num(r.opt_min, 1), num(r.opt_max, 1)
            notes.append(
                Text(
                    f"Soil pH {ph.en} (soil map) is a bit outside the best range for {al.en} "
                    f"({lo.en}-{hi.en}); expect somewhat lower yields in any month. A soil test "
                    "can confirm it",
                    f"El pH del suelo {ph.es} (mapa de suelos) está un poco fuera del rango ideal "
                    f"para {crop.the_es} ({lo.es}-{hi.es}); puede rendir algo menos en "
                    "cualquier mes. Un análisis de suelo lo confirma",
                )
            )
    return notes


def planting_windows(
    ctx: AppContext, lat: float, lon: float, crop_ids: list[str] | None
) -> s.PlantingWindowsResponse:
    """Best sowing months per crop at a point, scored with the MVP priorities and variables."""
    ctx.check_location(lat, lon)
    crops = ctx.resolve_crops(crop_ids)
    climate = ctx.sources.climate.monthly_climate(lat, lon)
    soil = ctx.sources.soil.soil(lat, lon)
    p = ctx.config.priority_weights
    weights = Weights(water=p.water, soil=p.soil, climate=p.climate)
    result = []
    for crop in crops:
        months = sowing_calendar(
            crop, climate=climate, soil=soil, weights=weights, variables=ctx.config.variables
        )
        result.append(
            s.CropPlanting(
                crop_id=crop.id,
                crop_name=crop.name,
                cycle_days=crop.cycle_days,
                sowing_months=[
                    s.SowingMonth(
                        sowing_month=m.sowing_month,
                        months_in_field=list(m.fit.season.months),
                        score=_score(m.score),
                        is_good=m.is_good(),
                        waterlogging_risk=m.fit.waterlogging_warning,
                        dry_month_note=_lt_or_none(_dry_month_note(crop, m)),
                        limiting_factor=_limiting_factor(m.fit.variable_scores),
                        variable_scores={k: _score(v) for k, v in m.fit.variable_scores.items()},
                    )
                    for m in months
                ],
                fixed_limits=[_lt(t) for t in _fixed_limit_notes(crop, soil, fixed_limits(months))],
                windows=[
                    s.PlantingWindow(
                        first_month=w.first_month,
                        last_month=w.last_month,
                        best_month=w.best_month,
                        best_score=_score(w.best_score),
                    )
                    for w in find_planting_windows(months)
                ],
            )
        )
    return s.PlantingWindowsResponse(
        location=s.Location(lat=lat, lon=lon),
        crops=result,
        data_sources=s.DataSources(**ctx.sources.names()),
    )


# ---------------------------------------------------------------- permanent crops

_PERMANENT_CROP_GAPS = (
    Text(
        "Climate comes from NASA POWER monthly averages over a square about 50 km wide, not "
        "measured on your farm",
        "El clima viene de promedios mensuales de NASA POWER para un cuadro de unos 50 km de "
        "lado, no se midió en su finca",
    ),
    Text(
        "Scored on climate and soil pH only: no yields, years to the first harvest, shade, pests, "
        "diseases or prices",
        "Solo se evalúan el clima y el pH del suelo: no incluye rendimientos, años hasta la "
        "primera cosecha, sombra, plagas, enfermedades ni precios",
    ),
    Text(
        "Soil drainage and soil moisture are not scored for permanent crops",
        "El drenaje y la humedad del suelo no se evalúan para cultivos permanentes",
    ),
)


def _altitude_gap(crops: Sequence[PerennialCropProfile]) -> Text | None:
    """Altitude matters (cacao stops at ~900 m) but the API has no elevation for the point."""
    limits = [(c, c.max_altitude_m) for c in crops if c.max_altitude_m is not None]
    if not limits:
        return None
    en = ", ".join(f"{c.label.en.lower()} up to {num(m).en} m" for c, m in limits)
    es = ", ".join(f"{c.label.es.lower()} hasta {num(m).es} m" for c, m in limits)
    return Text(
        f"Altitude is not checked. EcoCrop grows {en}: compare with your farm's altitude",
        f"No se revisa la altura. Según EcoCrop se siembra {es}: compárelo con la altura de su "
        "finca",
    )


def _permanent_crop_schema(fit: PerennialFit, dry_note: Text | None) -> s.PermanentCropFit:
    risks = [*fit.risks, *([dry_note] if dry_note is not None else [])]
    return s.PermanentCropFit(
        crop_id=fit.crop.id,
        crop_name=_lt(fit.crop.label),
        scientific_name=fit.crop.scientific_name,
        score=_score(fit.score),
        suitability=fit.suitability,
        variable_scores={k: _score(v) for k, v in fit.variable_scores.items()},
        breakdown=s.CategoryBreakdown(
            climate=_score(fit.categories.climate),
            water=_score(fit.categories.water),
            soil=_score(fit.categories.soil),
        ),
        max_altitude_m=fit.crop.max_altitude_m,
        summary=_lt(perennial_summary(fit)),
        risks=[_lt(t) for t in risks],
        benefits=[_lt(t) for t in fit.benefits],
    )


def permanent_crops(
    ctx: AppContext, lat: float, lon: float, crop_ids: list[str] | None
) -> s.PermanentCropsResponse:
    """Permanent crops (cacao, coffee…) at a point, scored on the whole year, best first."""
    ctx.check_location(lat, lon)
    crops = ctx.resolve_permanent_crops(crop_ids)  # unknown ids → 422 before any fetch
    climate = ctx.sources.climate.monthly_climate(lat, lon)
    soil = ctx.sources.soil.soil(lat, lon)
    year = year_climate(climate)
    fits = rank_perennials(
        [perennial_fit(crop=c, year=year, soil=soil, variables=ctx.config.variables) for c in crops]
    )
    dry_note = dry_season_note(year)
    altitude = _altitude_gap(crops)
    return s.PermanentCropsResponse(
        location=s.Location(lat=lat, lon=lon),
        year_climate=s.YearClimateSummary(
            annual_rainfall_mm=round(year.annual_rainfall_mm, 1),
            temperature_c=round(year.temperature_c, 2),
            hottest_month_max_c=round(year.hottest_month_max_c, 2),
            coldest_month_min_c=round(year.coldest_month_min_c, 2),
            dry_months=list(year.dry_months),
        ),
        crops=[_permanent_crop_schema(f, dry_note) for f in fits],
        data_sources=s.DataSources(
            climate=ctx.sources.climate.name,
            soil=ctx.sources.soil.name,
            crops=ctx.sources.perennials.name,
        ),
        data_gaps=[
            _lt(t) for t in (*_PERMANENT_CROP_GAPS, *([altitude] if altitude is not None else []))
        ],
    )


# ---------------------------------------------------------------- soil profile (OpenLandMap)

SOIL_SOURCE_LABELS = {"openlandmap": "OpenLandMap", "mock": "mock"}
# Units of every property in SoilLayerResult, returned with the data so no client has to guess.
SOIL_UNITS = {
    "ph": "pH in water (1:1 soil:water)",
    "organic_carbon_g_kg": "g/kg",
    "clay_pct": "% of fine earth by weight",
    "sand_pct": "% of fine earth by weight",
    "silt_pct": "% of fine earth by weight (100 - clay - sand)",
    "bulk_density_kg_m3": "kg/m³ (fine earth)",
    "field_capacity_m3m3": "m³/m³ (volumetric water content at 33 kPa)",
    "texture_class": "USDA texture class",
}
WORLD_BBOX = (-180.0, -90.0, 180.0, 90.0)  # min_lon, min_lat, max_lon, max_lat


class SoilLayerResult(TypedDict):
    """One depth of get_soil_data(). None = no valid value at this pixel and depth (not guessed)."""

    ph: float | None
    organic_carbon_g_kg: float | None
    clay_pct: float | None
    sand_pct: float | None
    silt_pct: float | None  # None also when clay + sand > 100 % (see domain/soil.py)
    bulk_density_kg_m3: float | None
    field_capacity_m3m3: float | None
    texture_class: str | None  # e.g. "clay loam"


class SoilDataResult(TypedDict):
    """get_soil_data() output. GET /soil returns it as SoilProfileResponse (depths as a list)."""

    latitude: float  # as requested; the values are those of the 250 m pixel containing it
    longitude: float
    source: str  # "OpenLandMap" (or "mock" in mock mode)
    attribution: str  # credit line required by the CC-BY-SA 4.0 license
    resolution_m: int
    depths_cm: list[int]
    units: dict[str, str]  # property name → unit
    soil: dict[str, SoilLayerResult]  # "0cm", "10cm", "30cm"


def _round_or_none(x: float | None, ndigits: int) -> float | None:
    return None if x is None else round(x, ndigits)


def _soil_layer_result(layer: SoilLayer) -> SoilLayerResult:
    # Rounded to the source's real precision: pH steps of 0.1, carbon 5 g/kg, density 10 kg/m³.
    return {
        "ph": _round_or_none(layer.ph, 1),
        "organic_carbon_g_kg": _round_or_none(layer.organic_carbon_g_kg, 1),
        "clay_pct": _round_or_none(layer.clay_pct, 1),
        "sand_pct": _round_or_none(layer.sand_pct, 1),
        "silt_pct": _round_or_none(layer.silt_pct, 1),
        "bulk_density_kg_m3": _round_or_none(layer.bulk_density_kg_m3, 0),
        "field_capacity_m3m3": _round_or_none(layer.field_capacity_m3m3, 2),
        "texture_class": layer.texture_class,
    }


def check_coordinates(lat: float, lon: float) -> None:
    """Real coordinates only: finite, lat in -90..90, lon in -180..180."""
    min_lon, min_lat, max_lon, max_lat = WORLD_BBOX
    valid = math.isfinite(lat) and math.isfinite(lon)
    if not (valid and min_lat <= lat <= max_lat and min_lon <= lon <= max_lon):
        raise OutOfRegionError(
            f"Location ({lat}, {lon}) is not a valid coordinate "
            "(latitude -90 to 90, longitude -180 to 180)",
            details={"lat": lat, "lon": lon, "bbox": list(WORLD_BBOX)},
        )


@lru_cache
def _default_soil_source() -> SoilProfileSource:
    # Same choice as the app (data_mode from mvp.yaml / .env), built once per process.
    return build_sources(get_config(), get_env()).soil_profile


def get_soil_data(
    *, latitude: float, longitude: float, soil_source: SoilProfileSource | None = None
) -> SoilDataResult:
    """Soil properties at 0, 10 and 30 cm for a point, for suitability and rotation choices.

        soil_data = get_soil_data(latitude=9.93, longitude=-84.08)

    Source: OpenLandMap 250 m maps (Hengl et al.) through Google Earth Engine, one request for
    all 7 datasets x 3 depths, then cached per pixel forever (the maps never change). Values
    are the ones of the 250 m pixel that contains the point:
      - pH in water; organic carbon in g/kg (stored in steps of 5 g/kg, so ±2.5 g/kg);
        clay and sand in % by weight; bulk density in kg/m³; field capacity as volumetric
        water content at 33 kPa in m³/m³; USDA texture class name.
      - silt_pct = 100 - clay - sand, only when both are valid and add up to 100 % or less.
      - A masked pixel (sea, lake, ice, no prediction) gives None for that property, never a guess.

    `soil_source` defaults to the configured one (data_mode: mock, cached or live). Pass one to
    reuse an app's sources or a fake in tests. Served over HTTP by GET /soil
    (soil_profile_response). Raises OutOfRegionError for impossible coordinates.
    """
    check_coordinates(latitude, longitude)
    source = soil_source or _default_soil_source()
    profile = source.soil_profile(latitude, longitude)
    return {
        "latitude": latitude,
        "longitude": longitude,
        "source": SOIL_SOURCE_LABELS.get(source.name, source.name),
        "attribution": source.attribution,
        "resolution_m": source.resolution_m,
        "depths_cm": [layer.depth_cm for layer in profile.layers],
        "units": dict(SOIL_UNITS),
        "soil": {f"{layer.depth_cm}cm": _soil_layer_result(layer) for layer in profile.layers},
    }


# ------------------------------------------------------------------ POST /plan-risk
# Fixed history range (decisions.md 2026-11-15): a moving end date would change the cache key
# every month and the committed demo snapshot would stop matching. Move it on purpose, with a new
# snapshot. IMERG starts 2000-06-01.
PLAN_RISK_HISTORY_START = date(2000, 6, 1)
PLAN_RISK_HISTORY_END = date(2025, 12, 31)
ENSO_SOURCE = "NOAA CPC RONI (El Niño, ERSST v6)"
# Labels per history source name (like SOURCE_LABELS / SOIL_SOURCE_LABELS). Adding a source =
# adding a key here, not a branch in plan_risk().
PLAN_RISK_SOURCE_LABELS: dict[str, list[str]] = {
    "nasa_power": ["NASA GPM IMERG (rain)", "NASA POWER / MERRA-2 (temperature, soil wetness)"],
    "mock": ["mock"],
}
# Columns plan_risk() reads from the history DataFrame: the four the engine replays plus the
# MERRA-2 rain that _rain_source_gap compares. Any adapter column names come from
# nasa_power.HISTORY_COLUMNS; this is the subset the service depends on.
PLAN_RISK_HISTORY_COLUMNS = (
    "rainfall_mm",
    "rainfall_merra2_mm",
    "temperature_max_c",
    "temperature_min_c",
    "root_wetness",
)


def _daily_history(df: pd.DataFrame, start: date, end: date, source: str) -> DailyHistory:
    """Adapter DataFrame → the domain's consecutive-day tuples (missing days become NaN)."""
    days = pd.date_range(start, end, freq="D")
    full = df.set_index("date").reindex(days)
    for column in PLAN_RISK_HISTORY_COLUMNS:
        if column not in full.columns:
            raise SourceDataError(
                f"Daily history has no {column} column", details={"source": source}
            )
    return DailyHistory(
        start=start,
        rain_mm=tuple(float(v) for v in full["rainfall_mm"]),
        tmax_c=tuple(float(v) for v in full["temperature_max_c"]),
        tmin_c=tuple(float(v) for v in full["temperature_min_c"]),
        root_wetness=tuple(float(v) for v in full["root_wetness"]),
    )


def _mm_dd(month: int, day: int) -> str:
    return f"{month:02d}-{day:02d}"


def _plan_risk_planting(
    *,
    history: DailyHistory,
    crop: CropProfile,
    sowing: s.PlantingInput,
    mvp_crops: list[CropProfile],
    roni: EnsoIndex | None,
) -> tuple[s.PlanRiskPlanting, PlanRiskResult]:
    plan = stress_test(
        history=history, crop=crop, sowing_month=sowing.sowing_month, sowing_day=sowing.sowing_day
    )
    alternatives = (
        ()
        if plan.not_enough_history
        else find_alternatives(history=history, crop=crop, plan=plan, other_crops=mvp_crops)
    )
    harvest = harvest_day(sowing.sowing_month, sowing.sowing_day, crop.cycle_days)
    schema = s.PlanRiskPlanting(
        crop_id=crop.id,
        crop_name=_lt(crop.label),
        sowing_date=_mm_dd(sowing.sowing_month, sowing.sowing_day),
        harvest_date=_mm_dd(*harvest),
        failed_years=plan.failed_years,
        failure_rate=round(plan.failure_rate, 3),
        summary=_lt(plan_summary(plan, crop)),
        causes=[
            s.PlanRiskCause(
                cause=c.cause,
                severity=c.severity,
                years=list(c.years),
                count=len(c.years),
                explanation=_lt(plan_explanation(c)),
                actions=[_lt(a) for a in actions_for(c, crop)],
            )
            for c in plan.cause_summaries()
        ],
        years=[
            s.PlanRiskYear(
                year=y.year,
                outcome=y.outcome,
                causes=list(y.causes),
                enso=None if roni is None else year_phase(roni, y.year, sowing.sowing_month),
            )
            for y in plan.seasons
        ],
        enso_split=None if roni is None else _enso_split_schema(plan, roni),
        alternatives=[
            s.PlanAlternative(
                kind=a.kind,
                crop_id=a.crop.id,
                sowing_date=_mm_dd(a.result.sowing_month, a.result.sowing_day),
                failed_years=a.result.failed_years,
                failure_rate=round(a.result.failure_rate, 3),
                label=_lt(a.label),
            )
            for a in alternatives
        ],
    )
    return schema, plan


def _enso_split_schema(plan: PlanRiskResult, roni: EnsoIndex) -> s.EnsoSplit:
    split = enso_split(plan, roni)
    group = {p: s.EnsoGroup(years=c.years, failed=c.failed) for p, c in split.counts.items()}
    return s.EnsoSplit(
        el_nino=group["el_nino"],
        la_nina=group["la_nina"],
        neutral=group["neutral"],
        note=_lt(split.note),
    )


def _enso_index(ctx: AppContext, name: Literal["RONI", "ONI"]) -> EnsoIndex | None:
    """El Niño context is optional in the contract: if NOAA fails and nothing is cached, the
    response goes on without it (and says so in data_gaps) instead of failing the whole plan."""
    try:
        return ctx.sources.enso.index(name)
    except SourceError as e:
        log.warning("NOAA %s unavailable, plan-risk continues without it: %s", name, e)
        return None


def _enso_now(roni: EnsoIndex) -> s.EnsoNow:
    latest = roni.latest
    return s.EnsoNow(
        oni=latest.anomaly_c,
        phase=phase_of(latest.anomaly_c),
        season=f"{latest.season} {latest.year}",
        source=ENSO_SOURCE,
    )


def _enso_gaps(
    roni: EnsoIndex | None, oni: EnsoIndex | None, plans: list[PlanRiskResult]
) -> list[Text]:
    if roni is None:
        return [ENSO_UNAVAILABLE]
    gaps = [latest_estimate_note(roni)]
    if oni is not None:
        items = []
        for sowing_month in dict.fromkeys(p.sowing_month for p in plans):
            years = [y.year for p in plans if p.sowing_month == sowing_month for y in p.seasons]
            years = list(dict.fromkeys(years))
            differing = label_disagreements(roni, oni, years=years, month=sowing_month)
            items.append((differing, len(years), sowing_month))
        if items:
            gaps.append(disagreement_note(items))  # one line, not one per sowing month
    return gaps


def _rain_source_gap(df: pd.DataFrame) -> Text | None:
    """How far MERRA-2 rain differs from IMERG over the same days (plan-risk.md, phase 2)."""
    both = df[["rainfall_mm", "rainfall_merra2_mm"]].dropna()
    imerg = float(both["rainfall_mm"].sum())
    if both.empty or imerg <= 0:
        return None
    ratio = float(both["rainfall_merra2_mm"].sum()) / imerg
    if ratio >= 2:
        # "208% more rain" reads like a typo; above double, say so in words.
        amount = Text("more than twice as much", "más del doble de")
    else:
        p = pct(abs(ratio - 1))
        en_dir, es_dir = ("less", "menos") if ratio < 1 else ("more", "más")
        amount = Text(f"{p.en} {en_dir}", f"{p.es} {es_dir}")
    # Never "some years would come out differently": the years are not re-run with MERRA-2.
    return Text(
        f"A second NASA rain estimate (MERRA-2 computer model, about 50 km) shows {amount.en} "
        "rain here compared with the satellite, so take the rain numbers as approximate",
        f"Otra estimación de lluvia de la NASA (modelo MERRA-2, unos 50 km) da {amount.es} "
        "lluvia aquí que el satélite; tome las cifras de lluvia como aproximadas",
    )


def _plan_risk_data_gaps(
    df: pd.DataFrame,
    years: s.YearsEvaluated,
    plans: list[tuple[CropProfile, PlanRiskResult]],
    enso_gaps: list[Text],
) -> list[Text]:
    gaps = [
        Text(
            "Rain comes from NASA satellites (GPM IMERG): an average over a square about 10 km "
            "wide, not measured on your farm",
            "La lluvia viene de satélites de la NASA (GPM IMERG): es un promedio de un cuadro de "
            "unos 10 km de lado, no se midió en su finca",
        ),
        Text(
            "Temperature and soil wetness come from a NASA model (MERRA-2) over ~50 km",
            "La temperatura y la humedad del suelo vienen de un modelo de la NASA (MERRA-2) para "
            "~50 km",
        ),
        Text(
            f"Based on every year sown from {years.first} to {years.last} with complete data",
            f"Basado en cada año sembrado de {years.first} a {years.last} con datos completos",
        ),
        Text(
            "Weather patterns only: no yields, pests, diseases or prices, and it assumes no "
            "irrigation",
            "Solo patrones de clima: no incluye rendimientos, plagas, enfermedades ni precios, y "
            "supone que no hay riego",
        ),
        Text(
            "A 'failed' year means weather known to badly damage this crop (for example, "
            f"{FLOWERING_DRY_ALWAYS_FAIL_DAYS} days or more without rain at flowering). It is "
            "not a harvest measurement",
            "Un año 'fallado' es un año con un clima que daña mucho a este cultivo (por ejemplo, "
            f"{FLOWERING_DRY_ALWAYS_FAIL_DAYS} días o más sin lluvia en la floración). No es una "
            "medición de la cosecha",
        ),
        *enso_gaps,
    ]
    gap = _rain_source_gap(df)
    if gap is not None:
        gaps.append(gap)
    for crop, plan in plans:
        note = warm_nights_note(plan, crop)
        if note is not None and note not in gaps:
            gaps.append(note)
        if plan.not_enough_history:
            when = day_month(plan.sowing_month, plan.sowing_day)
            # Starts with the crop name: the frontend places it on that card.
            note = Text(
                f"{crop.label.en}, sown {when.en}: only {plan.evaluated} years with "
                "complete data, too few to judge",
                f"{crop.label.es}, siembra del {when.es}: solo {plan.evaluated} años con "
                "datos completos, muy pocos para juzgar",
            )
            if note not in gaps:  # the same planting may be listed twice
                gaps.append(note)
    return gaps


def plan_risk(ctx: AppContext, req: s.PlanRiskRequest) -> s.PlanRiskResponse:
    """Replay each planting against every past season of daily weather at the point."""
    ctx.check_location(req.lat, req.lon)
    ctx.resolve_crops([p.crop for p in req.plantings])  # unknown ids → 422 before any fetch
    catalog = ctx.sources.crops.all()
    mvp_crops = ctx.resolve_crops(None)
    start, end = PLAN_RISK_HISTORY_START, PLAN_RISK_HISTORY_END
    df = ctx.sources.history.daily_history(lat=req.lat, lon=req.lon, start=start, end=end)
    history = _daily_history(df, start, end, ctx.sources.history.name)
    roni, oni = _enso_index(ctx, "RONI"), _enso_index(ctx, "ONI")
    results = [
        _plan_risk_planting(
            history=history, crop=catalog[p.crop], sowing=p, mvp_crops=mvp_crops, roni=roni
        )
        for p in req.plantings
    ]
    seasons = [y.year for planting, _ in results for y in planting.years]
    years = s.YearsEvaluated(
        first=min(seasons, default=0),
        last=max(seasons, default=0),
        count=max((plan.evaluated for _, plan in results), default=0),
    )
    history_name = ctx.sources.history.name
    sources = PLAN_RISK_SOURCE_LABELS.get(history_name, [history_name])
    if roni is not None and history_name != "mock":
        sources = [*sources, ENSO_SOURCE]
    return s.PlanRiskResponse(
        location=s.Location(lat=req.lat, lon=req.lon),
        years_evaluated=years,
        data_sources=sources,
        enso_now=None if roni is None else _enso_now(roni),
        plantings=[planting for planting, _ in results],
        data_gaps=[
            _lt(t)
            for t in _plan_risk_data_gaps(
                df,
                years,
                [
                    (catalog[p.crop], plan)
                    for p, (_, plan) in zip(req.plantings, results, strict=True)
                ],
                _enso_gaps(roni, oni, [plan for _, plan in results]),
            )
        ],
    )


# ---------------------------------------------------------------- HTTP: weather, erosion, soil
# Thin adapters from the functions above to the API schemas. The logic stays in those functions.

RISK_LEVELS: dict[int, s.RiskLevel] = {
    ErosionRisk.LOW: "low",
    ErosionRisk.MEDIUM: "medium",
    ErosionRisk.HIGH: "high",
}


def _value_or_none(x: Any, ndigits: int) -> float | None:
    # pandas marks a missing day as NaN; the API says null.
    return None if pd.isna(x) else round(float(x), ndigits)


def daily_weather_response(ctx: AppContext, q: s.PointPeriodQuery) -> s.DailyWeatherResponse:
    """GET /weather/daily: the daily series from `Sources.daily` (NASA POWER, or mock)."""
    ctx.check_location(q.lat, q.lon)
    source = ctx.sources.daily
    df = source.daily_weather(lat=q.lat, lon=q.lon, start=q.start, end=q.end)
    missing = [None] * len(df)  # the mock source has no daily max / min columns

    def column(name: str) -> list[Any]:
        return df[name].tolist() if name in df.columns else missing

    rows = zip(
        df["date"],
        column("temperature_c"),
        column("temperature_max_c"),
        column("temperature_min_c"),
        column("rainfall_mm"),
        strict=True,
    )
    return s.DailyWeatherResponse(
        location=s.Location(lat=q.lat, lon=q.lon),
        start=q.start,
        end=q.end,
        source=source.name,
        days=[
            s.DailyWeather(
                date=day.date(),
                temperature_c=_value_or_none(t, 2),
                temperature_max_c=_value_or_none(t_max, 2),
                temperature_min_c=_value_or_none(t_min, 2),
                rainfall_mm=_value_or_none(rain, 2),
            )
            for day, t, t_max, t_min, rain in rows
        ],
    )


def erosion_response(ctx: AppContext, q: s.PointPeriodQuery) -> s.ErosionRiskResponse:
    """GET /erosion: erosion_risk() with the configured terrain and daily-weather sources."""
    ctx.check_location(q.lat, q.lon)
    r = erosion_risk(
        terrain_source=ctx.sources.terrain,
        weather_source=ctx.sources.daily,
        lat=q.lat,
        lon=q.lon,
        start=q.start,
        end=q.end,
    )
    return s.ErosionRiskResponse(
        location=s.Location(lat=q.lat, lon=q.lon),
        start=q.start,
        end=q.end,
        **r,
        terrain_erosion_level=RISK_LEVELS[r["terrain_erosion_risk"]],
        combined_erosion_level=RISK_LEVELS[r["combined_erosion_risk"]],
        data_sources=s.ErosionDataSources(
            terrain=ctx.sources.terrain.name, weather=ctx.sources.daily.name
        ),
    )


def soil_profile_response(ctx: AppContext, lat: float, lon: float) -> s.SoilProfileResponse:
    """GET /soil: get_soil_data() with the configured soil-profile source, depths as a list."""
    ctx.check_location(lat, lon)
    data = get_soil_data(latitude=lat, longitude=lon, soil_source=ctx.sources.soil_profile)
    return s.SoilProfileResponse(
        location=s.Location(lat=lat, lon=lon),
        source=data["source"],
        attribution=data["attribution"],
        resolution_m=data["resolution_m"],
        layers=[
            s.SoilProfileLayer(depth_cm=depth, **data["soil"][f"{depth}cm"])
            for depth in data["depths_cm"]
        ],
    )
