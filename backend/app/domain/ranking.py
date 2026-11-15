"""Rotation ranking (v0, pending review by the agro-logic subagent / agronomist).

A rotation is one crop per season, repeated every year, so transitions are cyclic
(the last season is followed by the first one of the next year).

score = mean(crop/season scores) + rotation adjustments / number of seasons, clamped to 0..1.
The adjustments come from the rotation rules in rotation_rules.py (monoculture, same family,
legume after a non-legume, two heavy feeders in a row, ...), applied to every consecutive pair.
A rotation is "viable" only if every crop/season score is > 0. Rules lower or raise the score,
they never make a rotation non-viable.

Each rotation carries plain-language `benefits` and `risks` for the farmer (T4.4, #29). `risks`
always ends with "Local review: ..." items: what this tool does not judge, for a local agronomist
or extension officer to check before acting. `benefits` is never empty: if nothing qualifies, it
says so.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from statistics import mean

from app.domain.models import (
    CategoryScores,
    CropProfile,
    CropSeasonFit,
    MonthlyClimate,
    RotationResult,
    Season,
    SoilConditions,
    Weights,
)
from app.domain.rotation_rules import judge_transition
from app.domain.suitability import crop_season_fit, season_climate
from app.domain.text import Text, num
from app.errors import DomainInvariantError

# A category (climate, water, soil) at or above this is listed as a benefit.
STRONG_CATEGORY = 0.8

# Said instead of an empty list (possible for monoculture or same family with a weak fit).
NO_BENEFIT = Text(
    "The rotation rules found no benefit and climate, water and soil are not especially good "
    "for these crops; compare with the other options",
    "Las reglas de rotación no encontraron ventajas y el clima, el agua y el suelo no les calzan "
    "especialmente bien; compárela con las otras opciones",
)
# What the score does not see. Always listed, so the farmer knows where local expertise is needed.
# Pests and diseases are only approximated by crop family (rotation_rules.py); slope and erosion
# (erosion.py) are not part of the ranking; seasons are rainfed (mvp.yaml); markets and labour are
# not modelled.
LOCAL_REVIEW_UNSCORED = Text(
    "Local review: actual pest and disease pressure (judged here only by crop family), field "
    "slope and erosion, irrigation, labour and market prices are not scored; ask a local "
    "agronomist or extension officer to check them for this field",
    "Revisión local: no se evaluaron la presión real de plagas y enfermedades (aquí solo se "
    "estima por familia), la pendiente y erosión, el riego, la mano de obra ni los precios; "
    "consúltelos con un técnico del MAG o un agrónomo de la zona",
)
# A category that scores well in every season is a benefit, in plain words (no numbers).
STRONG_CATEGORY_TEXT = {
    "climate": Text(
        "The climate suits these crops in every season",
        "El clima les sirve a estos cultivos en todas las épocas",
    ),
    "water": Text(
        "Rain and soil moisture suit these crops in every season",
        "La lluvia y la humedad del suelo les sirven a estos cultivos en todas las épocas",
    ),
    "soil": Text("The soil pH suits these crops", "El pH del suelo les sirve a estos cultivos"),
}
# Water scores strong but a waterlogging warning exists: say the rain is enough, not the soil.
WATER_ENOUGH_WATCH_DRAINAGE = Text(
    "There is enough rain for these crops, but watch drainage in the wettest months",
    "Hay lluvia suficiente para estos cultivos, pero vigile el drenaje en los meses más lluviosos",
)
# Short forms of the rotation rules for the one-sentence explanation.
RULE_SUMMARY = {
    "family_change": Text(
        "changing crop family cuts pest cycles", "cambiar de familia corta plagas"
    ),
    "legume_restores_nitrogen": Text(
        "the bean-family crop adds a little nitrogen", "la leguminosa aporta un poco de nitrógeno"
    ),
    "monoculture": Text(
        "repeating the same crop builds up pests", "repetir el mismo cultivo acumula plagas"
    ),
    "same_family": Text("same family shares pests", "la misma familia comparte plagas"),
    "heavy_after_heavy": Text(
        "both crops need a lot of nitrogen", "los dos cultivos piden mucho nitrógeno"
    ),
    "fungi_break": Text("fewer helpful soil fungi", "menos hongos buenos en el suelo"),
}
WATERLOGGING_SUMMARY = Text("risk of waterlogging", "riesgo de encharcamiento")

# Crops whose EcoCrop ranges are too broad for the tropics, so a high score alone can mislead.
# Potato: optimum 15-25 °C scores it 0.98 at Los Chiles (~26 °C) vs 0.83 at Cartago, where it is
# grown (decisions.md 2026-11-15). Shown as a risk until a cited tropical range replaces it.
CROP_CAVEATS: dict[str, Text] = {
    "potato": Text(
        "Potato: check your farm's altitude. Potato does best in cool highlands, such as the "
        "slopes of the Irazú volcano in Cartago. In warm lowlands it rarely does well, even when "
        "it scores high here, because the crop data behind the score is very broad for the tropics",
        "Papa: revise la altura de su finca. La papa se da mejor en zonas altas y frescas, como "
        "las faldas del volcán Irazú en Cartago. En zonas bajas y calientes casi nunca se da bien, "
        "aunque aquí salga con buen puntaje, porque los datos del cultivo que usamos son muy "
        "amplios para el trópico",
    ),
}


def crop_caveats(r: RotationResult) -> tuple[Text, ...]:
    """One caveat per crop in the rotation that has one (CROP_CAVEATS), in sequence order."""
    ids = dict.fromkeys(f.crop.id for f in r.sequence)
    return tuple(CROP_CAVEATS[i] for i in ids if i in CROP_CAVEATS)


def _mean_category(fits: Sequence[CropSeasonFit], name: str) -> float | None:
    vals = [getattr(f.categories, name) for f in fits]
    vals = [v for v in vals if v is not None]
    return mean(vals) if vals else None


def score_rotation(fits: Sequence[CropSeasonFit]) -> RotationResult:
    n = len(fits)
    base = mean(f.score for f in fits)
    adjustment = 0.0
    benefits: list[Text] = []
    risks: list[Text] = []
    rules: list[str] = []
    for i in range(n):
        judgement = judge_transition(fits[i - 1].crop, fits[i].crop)  # i-1 wraps around: cyclic
        adjustment += judgement.adjustment / n
        for hit in judgement.hits:
            (benefits if hit.effect == "benefit" else risks).append(hit.reason)
            rules.append(hit.rule)
    for f in fits:
        risks.extend(f.risks)
    breakdown = CategoryScores(
        climate=_mean_category(fits, "climate"),
        water=_mean_category(fits, "water"),
        soil=_mean_category(fits, "soil"),
    )
    waterlogged = any(f.waterlogging_warning for f in fits)
    for name, value in vars(breakdown).items():
        if value is None or value < STRONG_CATEGORY:
            continue
        if name == "water" and waterlogged:
            # "Water suits" next to a waterlogging warning would contradict it (farmer-language
            # review), so say only that the rain is enough.
            benefits.append(WATER_ENOUGH_WATCH_DRAINAGE)
        else:
            benefits.append(STRONG_CATEGORY_TEXT[name])
    risks.extend(local_review(fits))
    return RotationResult(
        sequence=tuple(fits),
        score=min(1.0, max(0.0, base + adjustment)),
        breakdown=breakdown,
        viable=all(f.score > 0 for f in fits),
        benefits=tuple(dict.fromkeys(benefits)) or (NO_BENEFIT,),  # dedupe, keep order
        risks=tuple(dict.fromkeys(risks)),
        rules_fired=tuple(dict.fromkeys(rules)),
    )


def local_review(fits: Sequence[CropSeasonFit]) -> list[Text]:
    """Where local expertise is needed before acting on this rotation. Never empty."""
    steps_en = ", ".join(f"{f.crop.label.en.lower()} in {f.season.name}" for f in fits)
    steps_es = ", ".join(f"{f.crop.label.es.lower()} en {f.season.name}" for f in fits)
    return [
        Text(
            f"Local review: check sowing dates and varieties for {steps_en}; the seasons here are "
            "fixed calendar months, not the local planting calendar",
            f"Revisión local: confirme fechas de siembra y variedades para {steps_es}; las épocas "
            "aquí son meses fijos del calendario, no el calendario de siembra de su zona",
        ),
        LOCAL_REVIEW_UNSCORED,
    ]


def rank_rotations(
    *,
    crops: Sequence[CropProfile],
    seasons: Sequence[Season],
    climate: MonthlyClimate,
    soil: SoilConditions,
    weights: Weights,
    variables: Sequence[str],
    top_n: int | None = 5,
) -> list[RotationResult]:
    """Every crop sequence over the seasons, best first (viable before non-viable).

    `top_n=None` returns all of them (used to place the farmer's current rotation).
    """
    if not crops:
        raise DomainInvariantError("Need at least one crop")
    if len(seasons) < 2:
        raise DomainInvariantError("Need at least two seasons to build a rotation")
    w = weights.normalized()
    climates = {s.name: season_climate(climate, s) for s in seasons}
    fit = {
        (c.id, s.name): crop_season_fit(c, climates[s.name], soil, w, variables)
        for c in crops
        for s in seasons
    }
    results = [
        score_rotation([fit[(c.id, s.name)] for c, s in zip(seq, seasons, strict=True)])
        for seq in itertools.product(crops, repeat=len(seasons))
    ]
    results.sort(key=lambda r: (not r.viable, -r.score, [f.crop.id for f in r.sequence]))
    return results if top_n is None else results[:top_n]


def explain(r: RotationResult) -> Text:
    """One plain-language sentence for the farmer: what helps, what to watch, the score."""
    names = Text(
        " → ".join(f"{f.crop.label.en} ({f.season.name})" for f in r.sequence),
        " → ".join(f"{f.crop.label.es} ({f.season.name})" for f in r.sequence),
    )
    if not r.viable:
        return Text(
            f"{names.en}: not recommended, at least one crop is outside what it tolerates in its "
            "season.",
            f"{names.es}: no se recomienda, al menos un cultivo queda fuera de lo que tolera en su "
            "época.",
        )
    helps = [RULE_SUMMARY[k] for k in r.rules_fired if k in RULE_SUMMARY and k in _BENEFIT_RULES]
    watch = [
        RULE_SUMMARY[k] for k in r.rules_fired if k in RULE_SUMMARY and k not in _BENEFIT_RULES
    ]
    if any(f.waterlogging_warning for f in r.sequence):
        watch.append(WATERLOGGING_SUMMARY)
    score = num(r.score, 2)
    help_en = ", ".join(t.en for t in helps) or "no rotation benefit"
    help_es = ", ".join(t.es for t in helps) or "sin ventajas de rotación"
    watch_en = f"; watch: {', '.join(t.en for t in watch)}" if watch else ""
    watch_es = f"; ojo: {', '.join(t.es for t in watch)}" if watch else ""
    return Text(
        f"{names.en}: {help_en}{watch_en}. Score {score.en} of 1.",
        f"{names.es}: {help_es}{watch_es}. Puntaje {score.es} de 1.",
    )


_BENEFIT_RULES = {"family_change", "legume_restores_nitrogen"}
