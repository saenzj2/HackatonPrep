"""Suitability of one crop in one season (v0, pending agronomic review: agro-logic subagent).

Method (inspired by the FAO EcoCrop model):
1. Each variable gets a 0..1 score from a trapezoid over the crop's tolerance range.
2. Variables are grouped into the farmer's priority categories:
      climate = temperature · water = rainfall, soil_moisture · soil = soil_ph
   A category score is the mean of its enabled variables.
3. The crop/season score is the priority-weighted mean of the available categories.
4. Limiting factor: if any variable is outside the crop's absolute range, the score is 0.

Known simplifications (logged in docs/decisions.md):
- Uses the mean temperature only (no frost/heat-stress days from T2M_MIN/T2M_MAX yet).
- Crop-cycle rainfall = mean monthly rainfall of the season × cycle length.
- Soil moisture uses one generic range for all crops (EcoCrop has no moisture data).
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from statistics import mean

from app.domain.models import (
    CategoryScores,
    CropProfile,
    CropSeasonFit,
    MonthlyClimate,
    Range,
    Season,
    SeasonClimate,
    SoilConditions,
    Weights,
)

DAYS_PER_MONTH = 30.44

# Generic volumetric soil moisture tolerance (m³/m³). TODO(agro-logic): per-crop values.
GENERIC_SOIL_MOISTURE = Range(abs_min=0.05, opt_min=0.20, opt_max=0.40, abs_max=0.55)

CATEGORY_OF = {
    "temperature": "climate",
    "rainfall": "water",
    "soil_moisture": "water",
    "soil_ph": "soil",
}


def trapezoid(x: float, r: Range) -> float:
    """1 inside the optimal range, linear down to 0 at the absolute limits, 0 outside."""
    if x <= r.abs_min or x >= r.abs_max:
        return 0.0
    if r.opt_min <= x <= r.opt_max:
        return 1.0
    if x < r.opt_min:
        return (x - r.abs_min) / (r.opt_min - r.abs_min)
    return (r.abs_max - x) / (r.abs_max - r.opt_max)


def season_climate(climate: MonthlyClimate, season: Season) -> SeasonClimate:
    idx = [m - 1 for m in season.months]
    return SeasonClimate(
        season=season,
        temperature_c=mean(climate.temperature_c[i] for i in idx),
        rainfall_mm_per_month=mean(climate.rainfall_mm[i] for i in idx),
    )


def cycle_rainfall_mm(sc: SeasonClimate, crop: CropProfile) -> float:
    return sc.rainfall_mm_per_month * crop.cycle_days / DAYS_PER_MONTH


def _mean_or_none(values: Iterable[float]) -> float | None:
    vals = list(values)
    return mean(vals) if vals else None


def weighted_score(categories: CategoryScores, weights: Weights) -> float:
    """Weighted mean of the categories that have a value; weights of missing ones are dropped."""
    candidates = [
        (categories.climate, weights.climate),
        (categories.water, weights.water),
        (categories.soil, weights.soil),
    ]
    pairs = [(s, w) for s, w in candidates if s is not None]
    total_w = sum(w for _, w in pairs)
    if not pairs or total_w == 0:
        # All weight is on categories with no enabled variables: fall back to equal weights.
        return mean(s for s, _ in pairs) if pairs else 0.0
    return sum(s * w for s, w in pairs) / total_w


def crop_season_fit(
    crop: CropProfile,
    sc: SeasonClimate,
    soil: SoilConditions,
    weights: Weights,
    variables: Sequence[str],
) -> CropSeasonFit:
    rain = cycle_rainfall_mm(sc, crop)
    raw = {
        "temperature": (sc.temperature_c, crop.temperature_c, "°C"),
        "rainfall": (rain, crop.rainfall_mm, "mm/cycle"),
        "soil_ph": (soil.ph, crop.soil_ph, ""),
        "soil_moisture": (soil.moisture_m3m3, GENERIC_SOIL_MOISTURE, "m³/m³"),
    }
    scores: dict[str, float] = {}
    notes: list[str] = []
    for var in variables:
        value, rng, unit = raw[var]
        s = trapezoid(value, rng)
        scores[var] = s
        if s == 0.0:
            side = "below" if value <= rng.abs_min else "above"
            limit = rng.abs_min if side == "below" else rng.abs_max
            notes.append(
                f"{crop.name} in {sc.season.name}: {var} {value:.1f}{unit} is {side} "
                f"the absolute limit ({limit:g}{unit})"
            )

    categories = CategoryScores(
        climate=_mean_or_none(s for v, s in scores.items() if CATEGORY_OF[v] == "climate"),
        water=_mean_or_none(s for v, s in scores.items() if CATEGORY_OF[v] == "water"),
        soil=_mean_or_none(s for v, s in scores.items() if CATEGORY_OF[v] == "soil"),
    )
    score = 0.0 if any(s == 0.0 for s in scores.values()) else weighted_score(categories, weights)

    season_days = len(sc.season.months) * DAYS_PER_MONTH
    if crop.cycle_days > season_days:
        notes.append(
            f"{crop.name} cycle ({crop.cycle_days} d) is longer than {sc.season.name} "
            f"(~{season_days:.0f} d)"
        )
    return CropSeasonFit(
        crop=crop,
        season=sc.season,
        variable_scores=scores,
        categories=categories,
        score=score,
        notes=tuple(notes),
    )
