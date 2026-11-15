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
from app.domain.text import Text, num, pct

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
# Los Chiles 0.87, Alajuela 0.95). Placeholders.
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
        "temperature": (sc.temperature_c, crop.temperature_c),
        "rainfall": (rain, crop.rainfall_mm),
        "soil_ph": (soil.ph, crop.soil_ph),
        "soil_moisture": (soil.moisture_for(sc.season.months), GENERIC_SOIL_MOISTURE),
        "heat": (sc.temperature_max_c, heat_range(crop)),
        "frost": (sc.temperature_min_c, FROST_RANGE),
    }
    where = _where(crop, sc.season.name)
    scores: dict[str, float] = {}
    risks: list[Text] = []
    for var in variables:
        value, rng = raw[var]
        s = trapezoid(value, rng)
        scores[var] = s
        risk = _risk_note(where, var=var, value=value, rng=rng, score=s)
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
            risks.append(_waterlogging_note(where, crop, wetness, soil.texture_class))

    season_days = len(sc.season.months) * DAYS_PER_MONTH
    if crop.cycle_days > season_days:
        a, d, sd = crop.label, crop.cycle_days, f"{season_days:.0f}"
        season = sc.season.name
        risks.append(
            Text(
                f"{a.en} needs about {d} days but {season} lasts about {sd}: the harvest falls "
                "in the dry months, or use a shorter-cycle variety",
                f"{_cap(crop.the_es)} necesita unos {d} días y la {season} dura unos {sd}: la "
                "cosecha caería en verano, o use una variedad más precoz",
            )
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


# Textures that drain slowly (clay loam drains moderately, so it isn't flagged), with Spanish names.
SLOW_DRAINING_TEXTURES = {
    "clay": "arcilloso",
    "silty clay": "arcillo-limoso",
    "sandy clay": "arcillo-arenoso",
}

# Farmer-facing names and units of the scored variables.
VARIABLE_LABELS = {
    "temperature": (Text("average temperature", "temperatura promedio"), " °C", 1),
    "rainfall": (Text("rain over the crop cycle", "lluvia durante el ciclo"), " mm", 0),
    "soil_ph": (Text("soil pH", "pH del suelo"), "", 1),
}


def _cap(s: str) -> str:
    """'el maíz' → 'El maíz'."""
    return s[:1].upper() + s[1:]


def _where(crop: CropProfile, season: str) -> Text:
    """'Maize in primera' / 'Maíz en primera': how every crop/season note starts."""
    return Text(f"{crop.label.en} in {season}", f"{crop.label.es} en {season}")


def _waterlogging_note(where: Text, crop: CropProfile, wetness: float, texture: str | None) -> Text:
    """Coarse, modelled data: say so, never claim a field measurement."""
    share = pct(wetness)
    slow = SLOW_DRAINING_TEXTURES.get((texture or "").lower())
    clay_en = f" The soil map shows {texture}, which can drain slowly." if slow else ""
    clay_es = f" El mapa de suelos indica suelo {slow}, que puede drenar lento." if slow else ""
    return Text(
        f"{where.en}: risk of waterlogged soil. Satellite data for the area (~9 km) shows the soil "
        f"near saturation ({share.en} on average), and {crop.label.lower().en} doesn't tolerate "
        f"standing water.{clay_en} Check how your field drains; raised beds help.",
        f"{where.es}: riesgo de encharcamiento. Los datos satelitales de la zona (~9 km) muestran "
        f"el suelo casi saturado ({share.es} en promedio) y {crop.the_es} no aguanta "
        f"el agua empozada.{clay_es} Revise cómo drena su terreno; sembrar en lomillos o camas "
        "levantadas ayuda.",
    )


def _risk_note(where: Text, *, var: str, value: float, rng: Range, score: float) -> Text | None:
    """Plain-language risk for one variable, or None when the variable is not a concern."""
    if var in _OWN_WORDING:
        return _stress_note(where, var=var, value=value, rng=rng, score=score)
    label, unit, decimals = VARIABLE_LABELS[var]
    v = num(value, decimals)
    if score == 0.0:
        low = value <= rng.abs_min
        limit = num(rng.abs_min if low else rng.abs_max, decimals)
        if low:
            return Text(
                f"{where.en}: {label.en} too low (~{v.en}{unit}; needs at least {limit.en}{unit})",
                f"{where.es}: {label.es} muy por debajo de lo necesario (~{v.es}{unit}; necesita "
                f"al menos {limit.es}{unit})",
            )
        return Text(
            f"{where.en}: {label.en} too high (~{v.en}{unit}; tolerates up to {limit.en}{unit})",
            f"{where.es}: {label.es} por encima de lo que tolera (~{v.es}{unit}; aguanta hasta "
            f"{limit.es}{unit})",
        )
    if score < MARGINAL_SCORE:
        lo, hi = num(rng.opt_min, decimals), num(rng.opt_max, decimals)
        return Text(
            f"{where.en}: {label.en} ~{v.en}{unit}, outside the best range "
            f"({lo.en} to {hi.en}{unit})",
            f"{where.es}: {label.es} ~{v.es}{unit}, fuera del rango ideal "
            f"({lo.es} a {hi.es}{unit})",
        )
    return None


_OWN_WORDING = {"heat", "frost", "soil_moisture"}  # variables with their own plain-language note


def _stress_note(where: Text, *, var: str, value: float, rng: Range, score: float) -> Text | None:
    """Heat, frost and dry soil, worded for a farmer instead of as a range check."""
    v = num(value, 1)
    if var == "heat" and score < 1.0:
        limit = num(rng.opt_max, 0)
        return Text(
            f"{where.en}: strong heat, the average daily high ({v.en} °C) is above what the crop "
            f"tolerates ({limit.en} °C)",
            f"{where.es}: calor fuerte, la máxima promedio ({v.es} °C) supera lo que aguanta el "
            f"cultivo ({limit.es} °C)",
        )
    if var == "frost" and score < 1.0:
        safe = num(FROST_SAFE_C, 0)
        return Text(
            f"{where.en}: frost risk, the coldest month's average low is {v.en} °C (safe at "
            f"{safe.en} °C or above)",
            f"{where.es}: riesgo de helada, la mínima promedio del mes más frío es {v.es} °C (sin "
            f"riesgo desde {safe.es} °C)",
        )
    if var == "soil_moisture" and score < MARGINAL_SCORE:
        very = score == 0.0
        return Text(
            f"{where.en}: satellite data for the area (~9 km) shows "
            f"{'very' if very else 'fairly'} dry soil around the roots; the crop may lack water "
            "without irrigation",
            f"{where.es}: los datos satelitales de la zona (~9 km) muestran el suelo "
            f"{'muy' if very else 'algo'} seco donde están las raíces; el cultivo podría sufrir "
            "falta de agua si no se riega",
        )
    return None
