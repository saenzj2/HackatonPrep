"""Suitability of one crop in one season (v0, pending agronomic review: agro-logic subagent).

Method (inspired by the FAO EcoCrop model):
1. Each variable gets a 0..1 score from a trapezoid over the crop's tolerance range.
2. Variables are grouped into the farmer's priority categories:
      climate = temperature · water = rainfall, soil_moisture · soil = soil_ph
   A category score is the mean of its enabled variables.
3. The crop/season score is the priority-weighted mean of the available categories.
4. Limiting factor: if any variable is outside the crop's absolute range, the score is 0.

Stress variables (climate category), from monthly normals of daily max/min temperature:
- heat:  season mean daily max vs the crop's absolute max temperature. 1 at or below it,
         linear down to 0 at abs_max + HEAT_MARGIN_C.
- frost: daily min of the season's coldest month. 0 at or below FROST_C, 1 from FROST_SAFE_C up.

Known simplifications (logged in docs/decisions.md):
- Heat/frost use monthly normals, not counts of hot or frost days.
- Frost uses one generic range for all crops.
- Crop-cycle rainfall = mean monthly rainfall of the season × cycle length.
- Soil moisture (NASA SMAP root zone) only penalises DRY soil, with one generic range for all crops.
  Too much water is covered by each crop's rainfall upper limits, and by the waterlogging check
  for crops that need good drainage (agro-logic review 2026-11-15).
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

# Root-zone soil moisture (m³/m³), dry side only: 0 at or below 0.10 (near wilting for most soils),
# 1 from 0.20. No upper limit: SMAP's absolute values depend on its model's soil, so "too wet" isn't
# judged here (see WATERLOGGING_WETNESS). Placeholders, agro-logic review 2026-11-15.
_NO_UPPER_LIMIT_M3M3 = 1.0  # volumetric water content can't exceed 1
GENERIC_SOIL_MOISTURE = Range(
    abs_min=0.10, opt_min=0.20, opt_max=_NO_UPPER_LIMIT_M3M3, abs_max=_NO_UPPER_LIMIT_M3M3
)

# Waterlogging, only for crops that need good drainage (EcoCrop), from the cycle's mean root-zone
# wetness (NASA SMAP relative saturation, 0..1): no effect up to START, then the score drops
# linearly to MIN_FACTOR at FULL. A note from NOTE up. Never a veto: ~9 km monthly data can't see
# a field's drainage. At most -15 %: a real waterlogging event costs more, but only in poorly
# drained fields, which the data can't tell apart (agro-logic reviews 2026-11-15; real peaks:
# San Carlos 0.87, Alajuela 0.95). Placeholders.
WATERLOGGING_START = 0.80
WATERLOGGING_FULL = 0.95
WATERLOGGING_MIN_FACTOR = 0.85
WATERLOGGING_NOTE = 0.85

# Heat stress: °C above the crop's absolute max at which the mean daily max scores 0.
HEAT_MARGIN_C = 6.0
# Frost risk on the coldest month's mean daily minimum (°C). TODO(agro-logic): per-crop values.
FROST_C = 0.0
FROST_SAFE_C = 5.0
_NO_UPPER_LIMIT_C = 100.0  # frost has no upper limit; trapezoid needs one
_NO_LOWER_LIMIT_C = -100.0  # heat has no lower limit
FROST_RANGE = Range(FROST_C, FROST_SAFE_C, _NO_UPPER_LIMIT_C, _NO_UPPER_LIMIT_C)

# A variable scoring above 0 but below this is reported as a risk ("marginal").
MARGINAL_SCORE = 0.5

CATEGORY_OF = {
    "temperature": "climate",
    "heat": "climate",
    "frost": "climate",
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
        temperature_max_c=mean(climate.temperature_max_c[i] for i in idx),
        temperature_min_c=min(climate.temperature_min_c[i] for i in idx),
    )


def heat_range(crop: CropProfile) -> Range:
    """Tolerance for the season's mean daily maximum: fine up to the crop's absolute max."""
    limit = crop.temperature_c.abs_max
    return Range(_NO_LOWER_LIMIT_C, _NO_LOWER_LIMIT_C, limit, limit + HEAT_MARGIN_C)


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
        "soil_moisture": (soil.moisture_for(sc.season.months), GENERIC_SOIL_MOISTURE, "m³/m³"),
        "heat": (sc.temperature_max_c, heat_range(crop), "°C"),
        "frost": (sc.temperature_min_c, FROST_RANGE, "°C"),
    }
    scores: dict[str, float] = {}
    risks: list[str] = []
    for var in variables:
        value, rng, unit = raw[var]
        s = trapezoid(value, rng)
        scores[var] = s
        risk = _risk_note(crop, sc.season.name, var=var, value=value, rng=rng, unit=unit, score=s)
        if risk:
            risks.append(risk)

    categories = CategoryScores(
        climate=_mean_or_none(s for v, s in scores.items() if CATEGORY_OF[v] == "climate"),
        water=_mean_or_none(s for v, s in scores.items() if CATEGORY_OF[v] == "water"),
        soil=_mean_or_none(s for v, s in scores.items() if CATEGORY_OF[v] == "soil"),
    )
    score = 0.0 if any(s == 0.0 for s in scores.values()) else weighted_score(categories, weights)

    factor = 1.0
    warning = False
    wetness = soil.wetness_for(sc.season.months)
    if "soil_moisture" in variables and crop.needs_good_drainage and wetness is not None:
        factor = waterlogging_factor(wetness)
        score *= factor
        warning = wetness >= WATERLOGGING_NOTE
        if warning:
            texture = soil.texture_class
            clay_note = (
                f"; {texture} soil drains slowly, which raises the risk"
                if texture is not None and "clay" in texture.lower()
                else ""
            )
            risks.append(
                f"{crop.name} in {sc.season.name}: waterlogging risk, root zone {wetness:.0%} "
                f"saturated on average (NASA SMAP) and {crop.name} needs well-drained soil"
                f"{clay_note}; check drainage or use raised beds"
            )

    season_days = len(sc.season.months) * DAYS_PER_MONTH
    if crop.cycle_days > season_days:
        risks.append(
            f"{crop.name} cycle ({crop.cycle_days} d) is longer than {sc.season.name} "
            f"(~{season_days:.0f} d)"
        )
    return CropSeasonFit(
        crop=crop,
        season=sc.season,
        variable_scores=scores,
        categories=categories,
        score=score,
        risks=tuple(risks),
        waterlogging_factor=factor,
        waterlogging_warning=warning,
    )


def waterlogging_factor(wetness: float) -> float:
    """Score multiplier: 1 up to WATERLOGGING_START, then linear down to WATERLOGGING_MIN_FACTOR
    at WATERLOGGING_FULL and above."""
    if wetness <= WATERLOGGING_START:
        return 1.0
    share = min(1.0, (wetness - WATERLOGGING_START) / (WATERLOGGING_FULL - WATERLOGGING_START))
    return 1.0 - share * (1.0 - WATERLOGGING_MIN_FACTOR)


def _risk_note(
    crop: CropProfile,
    season: str,
    *,
    var: str,
    value: float,
    rng: Range,
    unit: str,
    score: float,
) -> str | None:
    """Plain-language risk for one variable, or None when the variable is not a concern."""
    where = f"{crop.name} in {season}"
    if var in _OWN_WORDING:
        return _stress_note(where, var=var, value=value, rng=rng, unit=unit, score=score)
    if score == 0.0:
        side = "below" if value <= rng.abs_min else "above"
        limit = rng.abs_min if side == "below" else rng.abs_max
        return f"{where}: {var} {value:.1f}{unit} is {side} the absolute limit ({limit:g}{unit})"
    if score < MARGINAL_SCORE:
        return (
            f"{where}: {var} {value:.1f}{unit} is marginal "
            f"(optimal {rng.opt_min:g} to {rng.opt_max:g}{unit})"
        )
    return None


_OWN_WORDING = {"heat", "frost", "soil_moisture"}  # variables with their own plain-language note


def _stress_note(
    where: str, *, var: str, value: float, rng: Range, unit: str, score: float
) -> str | None:
    """Heat, frost and dry soil, worded for a farmer instead of as a range check."""
    if var == "heat" and score < 1.0:
        return (
            f"{where}: heat stress, average daily max {value:.1f}{unit} is above the crop's "
            f"limit ({rng.opt_max:g}{unit})"
        )
    if var == "frost" and score < 1.0:
        return (
            f"{where}: frost risk, coldest month's average daily min is {value:.1f}{unit} "
            f"(safe from {FROST_SAFE_C:g}{unit})"
        )
    if var == "soil_moisture" and score < MARGINAL_SCORE:
        severity = "very dry, near the wilting point" if score == 0.0 else "dry"
        return (
            f"{where}: root-zone soil is {severity} (NASA SMAP, about {value:.2f} m³/m³); "
            "expect water stress without irrigation"
        )
    return None
