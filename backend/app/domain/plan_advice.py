"""What to do about a risky plan: actions per failure cause, and alternatives that failed less.

Actions are short, concrete, bilingual (Costa Rica) and never promise an outcome. Alternatives
re-run the same stress test (plan_risk.stress_test) with the sowing date shifted, or with another
MVP crop on the same date, and keep only options that failed in a smaller share of years.

Pure: no I/O. Every action carries its source in a comment; items marked "from memory,
unverified" are for the fact-checker (docs/decisions.md).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import timedelta
from typing import Literal

from app.domain.models import CropProfile
from app.domain.plan_risk import (
    Cause,
    CauseSummary,
    DailyHistory,
    PlanRiskResult,
    sowing_date,
    stages,
    stress_test,
    too_wet_for,
    warm_nights_are_typical,
)
from app.domain.text import Text, month, num

# --- Actions ---------------------------------------------------------------------------------
# Sources checked by the fact-checker on 2026-11-15 (decisions.md); "no source" = common practice.
_MULCH = Text(
    "Keep the soil covered with crop residue (mulch) to hold moisture",
    "Mantenga el suelo cubierto con rastrojo para conservar la humedad",
)  # Verified: FAO Conservation Agriculture, "Soil organic cover" (mulch inhibits evaporation)
_EARLY_VARIETY = Text(
    "Use an early (short-cycle) variety so the crop needs fewer weeks of good weather",
    "Use una variedad precoz (de ciclo corto) para que el cultivo necesite menos semanas de buen "
    "tiempo",
)  # Verified: drought escape = early flowering and maturity (Beebe et al. 2013, Front. Physiol.
# 4:35); e.g. the Costa Rican bean Nambí (INTA/UCR) is harvested at ~70 days

ACTIONS: dict[Cause, tuple[Text, ...]] = {
    "late_dry_start": (
        Text(
            "Sow only into moist soil (wet to a hand's depth). If the rains are ending, sow "
            "earlier rather than wait",
            "Siembre solo con el suelo húmedo (mojado a un palmo). Si las lluvias ya se están "
            "yendo, siembre antes en vez de esperar",
        ),  # Common-sense cue, no source for "a hand's depth"; onset rules (inspired by
        # Sivakumar 1988) wait for steady rain. "Sow earlier" covers late-season sowings, where
        # waiting makes it worse (farmer-language review 2026-11-15)
        Text(
            "Keep some seed back in case you have to re-sow",
            "Guarde algo de semilla por si tiene que resembrar",
        ),  # Common practice after false starts (no source found)
        _MULCH,
    ),
    "flowering_dry_spell": (
        Text(
            "Try a sowing date that puts flowering in wetter weeks",
            "Pruebe una fecha de siembra que ponga la floración en semanas más lluviosas",
        ),  # Follows from this point's own history (the alternatives)
        _EARLY_VARIETY,
        _MULCH,
    ),
    "cycle_rain_low": (
        _EARLY_VARIETY,
        Text(
            "Control weeds early: they compete with the crop for water",
            "Controle las malezas a tiempo: compiten con el cultivo por el agua",
        ),  # Verified: FAO weed management (a0884e), weeds compete for light, nutrients and
        # water; critical period ≈ the first third of the cycle
        Text(
            "If you can irrigate, save water for flowering, the stage that needs it most",
            "Si puede regar, guarde el agua para la floración, la etapa que más la necesita",
        ),  # Verified: FAO crop information (maize), flowering is the most water-sensitive stage
    ),
    "harvest_wet": (
        Text(
            "Harvest as soon as the grain is mature and finish drying it under cover",
            "Coseche apenas el grano esté maduro y termine de secarlo bajo techo",
        ),  # Partly sourced: FAO "Prevention of post-harvest food losses" (AC301E), long field
        # drying in wet weather invites moulds and pests
        Text(
            "Next season, sow on raised beds (lomillos) and dig drainage channels so water "
            "doesn't pool",
            "En la próxima siembra, siembre en lomillos y haga canales de drenaje para que el "
            "agua no se acumule",
        ),  # Verified term and effect: UCR bean trials (Agronomía Mesoamericana), lomillos
        # outyielded flat planting under web blight. Built at sowing, hence "next season".
    ),
    "flowering_heat": (
        Text(
            "Try a sowing date that puts flowering in cooler weeks",
            "Pruebe una fecha de siembra que ponga la floración en semanas menos calurosas",
        ),  # Follows from this point's own history (the alternatives)
        Text(
            "Ask the MAG extension agency or INTA about short-cycle or heat- and "
            "drought-tolerant varieties",
            "Pregunte en la agencia de extensión del MAG o en el INTA por variedades de ciclo "
            "corto o tolerantes al calor y la sequía",
        ),  # No heat-tolerant bean released in Costa Rica yet (CIAT lines only: Cruz et al.
        # 2023, Front. Plant Sci. 14:1145858); Nambí is short-cycle and drought-tolerant
    ),
}

# Extra, crop-specific actions (cause, crop id) → actions, shown before the generic ones.
CROP_ACTIONS: dict[tuple[Cause, str], tuple[Text, ...]] = {
    ("harvest_wet", "maize"): (
        Text(
            "Do the 'dobla': bend the stalk below the ear so the ear hangs down and sheds rain",
            "Haga la dobla: doble la caña debajo de la mazorca para que quede hacia abajo y "
            "escurra la lluvia",
        ),  # Verified: Munguía Ulloa 1995, Uniciencia (UNA), la dobla in Huetar Atlántica;
        # protects from rain, birds and wind; done ~30–40 days after silking
    ),
    ("harvest_wet", "beans"): (
        Text(
            "From flowering on, watch for web blight (mustia hilachosa) in rainy weeks; covering "
            "the soil with residue reduces rain splash",
            "Desde la floración, vigile la mustia hilachosa en semanas lluviosas; cubrir el "
            "suelo con rastrojo reduce el salpique",
        ),  # Verified: spread by rain splash, worse with rain; mulch / frijol tapado reduce it
        # (Galindo et al. 1983, Phytopathology 73:610-615, Costa Rica)
    ),
}

# Only "ask whether": no claim about what the insurance covers (plan-risk.md, phase 4).
# INS renamed "Seguro de Cosechas" to "Seguro Agrícola" in 2018 (El Mundo CR, 2018-03-13).
INSURANCE_ACTION = Text(
    "Ask INS whether its crop insurance (Seguro Agrícola) covers this risk for your crop",
    "Pregunte al INS si el Seguro Agrícola cubre este riesgo en su cultivo",
)


def actions_for(summary: CauseSummary, crop: CropProfile) -> tuple[Text, ...]:
    """What to do about one cause: crop-specific first, then generic, plus insurance for fails."""
    actions = CROP_ACTIONS.get((summary.cause, crop.id), ()) + ACTIONS[summary.cause]
    return (*actions, INSURANCE_ACTION) if summary.severity == "fail" else actions


# --- Summary and explanations ----------------------------------------------------------------
# Cause names mid-sentence ("mostly because of …"). Same wording as the frontend guide's labels.
CAUSE_LABELS: dict[Cause, Text] = {
    "late_dry_start": Text("a dry start after sowing", "un inicio seco después de la siembra"),
    "flowering_dry_spell": Text("dry spells at flowering", "sequías en la floración"),
    "cycle_rain_low": Text("too little rain over the cycle", "poca lluvia en el ciclo"),
    "harvest_wet": Text("rain at harvest", "lluvia en la cosecha"),
    "flowering_heat": Text("heat at flowering", "calor en la floración"),
}


def explanation(summary: CauseSummary) -> Text:
    """What happened in the worst year, with its numbers: 'Worst year, 2002: 23 days …'."""
    e = summary.worst.evidence
    y = summary.worst_year
    return Text(f"Worst year, {y}: {e.en}", f"El peor año, {y}: {e.es}")


def _main_fail_cause(plan: PlanRiskResult) -> Cause:
    """The cause behind the most failed years (ties: the order of cause_summaries)."""
    counts: dict[Cause, int] = {}
    for season in plan.seasons:
        for f in season.findings:
            if f.severity == "fail":
                counts[f.cause] = counts.get(f.cause, 0) + 1
    order = [c.cause for c in plan.cause_summaries()]
    return max(counts, key=lambda c: (counts[c], -order.index(c)))


def too_wet_summary(plan: PlanRiskResult, crop: CropProfile) -> Text:
    """'Too much rain for sorghum here: …' with the typical rain (rounded to 100 mm) and the
    crop's limit, attributed to FAO: EcoCrop's figure is an annual one applied per cycle here."""
    typical = num(round((plan.typical_cycle_rain_mm or 0.0) / 100) * 100)
    limit = num(crop.rainfall_mm.abs_max)
    name = crop.label.lower()
    return Text(
        f"Too much rain for {name.en} here: a typical season gets about {typical.en} mm over "
        f"the cycle, far above the {limit.en} mm upper limit FAO gives for {name.en}. "
        "Not recommended here.",
        f"Demasiada lluvia para {crop.the_es} aquí: en un ciclo típico caen unos {typical.es} mm, "
        f"muy por encima del límite de {limit.es} mm que da la FAO para {crop.the_es}. "
        "No se recomienda en este lugar.",
    )


def warm_nights_note(plan: PlanRiskResult, crop: CropProfile) -> Text | None:
    """A per-planting note (not a failure cause) when warm flowering nights are the norm here."""
    if not warm_nights_are_typical(plan, crop):
        return None
    typical = round(plan.typical_warm_flowering_nights or 0)
    total = len(stages(crop).flowering)
    name = crop.label
    when = day_month(plan.sowing_month, plan.sowing_day)
    # Starts with the crop name and the sowing date: the frontend places it on that card.
    return Text(
        f"{name.en}, sown {when.en}: at flowering, nights here are almost always above 20 °C "
        f"({typical} of {total} nights in a typical year). Warm nights make the plant set fewer "
        "pods. This is normal for this place, so it is not counted as a bad year; ask the MAG "
        "extension office about varieties that cope with heat",
        f"{name.es}, siembra del {when.es}: en la floración, aquí las noches casi siempre pasan "
        f"de 20 °C ({typical} de {total} noches en un año típico). Las noches calientes hacen que "
        "la planta pegue menos vainas. Es normal en este lugar, así que no se cuenta como año "
        "malo; consulte en la agencia de extensión del MAG por variedades que aguanten el calor",
    )


def plan_summary(plan: PlanRiskResult, crop: CropProfile) -> Text:
    """One sentence for the card headline. A crop that doesn't belong here is said first, even
    when the yearly checks found no failures (they judge a season, not whether the crop fits)."""
    total = plan.evaluated
    if plan.not_enough_history:
        return Text(
            f"Not enough complete seasons to judge this plan (only {total})",
            f"No hay suficientes temporadas completas para juzgar este plan (solo {total})",
        )
    if too_wet_for(plan, crop):
        return too_wet_summary(plan, crop)
    count = outcome_count(plan)
    if plan.failed_years:
        why = CAUSE_LABELS[_main_fail_cause(plan)]
        return Text(
            f"{count.en.capitalize()}, mostly because of {why.en}.",
            f"{count.es.capitalize()}, sobre todo por {why.es}.",
        )
    summaries = plan.cause_summaries()
    if not summaries:
        return Text(
            f"{count.en.capitalize()}, and no weather problems were found.",
            f"{count.es.capitalize()} y no se encontraron problemas de clima.",
        )
    top = summaries[0]
    n = len(top.years)
    label = CAUSE_LABELS[top.cause]
    return Text(
        f"{count.en.capitalize()}; watch for {label.en} ({n} of {total} years).",
        f"{count.es.capitalize()}; ojo con {label.es} ({n} de {total} años).",
    )


# --- Alternatives ----------------------------------------------------------------------------
# Shifts of the sowing date tried for the same crop (days). Placeholder (plan-risk.md, phase 4).
SOWING_SHIFTS_DAYS = (-28, -14, 14, 28)
MAX_ALTERNATIVES = 3
# Reference non-leap year to move a month/day by N days (the result has no year).
_REFERENCE_YEAR = 2001

AlternativeKind = Literal["shift_sowing", "other_crop"]


@dataclass(frozen=True)
class Alternative:
    kind: AlternativeKind
    crop: CropProfile
    shift_days: int  # 0 for another crop on the same date
    result: PlanRiskResult

    @property
    def label(self) -> Text:
        return alternative_label(self)


def shift_date(sowing_month: int, sowing_day: int, days: int) -> tuple[int, int]:
    """(month, day) moved by `days`, wrapping the year. Feb 29 counts as Feb 28."""
    moved = sowing_date(_REFERENCE_YEAR, sowing_month, sowing_day) + timedelta(days=days)
    return moved.month, moved.day


def day_month(sowing_month: int, sowing_day: int) -> Text:
    """'August 18' / '18 de agosto'."""
    m = month(sowing_month)
    return Text(f"{m.en} {sowing_day}", f"{sowing_day} de {m.es}")


def outcome_count(result: PlanRiskResult) -> Text:
    """'would have failed in 2 of 25 years' / 'habría fallado en 2 de 25 años'."""
    n, total = result.failed_years, result.evaluated
    if n == 0:
        return Text(
            f"would not have failed in any of the {total} years",
            f"no habría fallado en ninguno de los {total} años",
        )
    return Text(
        f"would have failed in {n} of {total} years", f"habría fallado en {n} de {total} años"
    )


def alternative_label(alt: Alternative) -> Text:
    when = day_month(alt.result.sowing_month, alt.result.sowing_day)
    count = outcome_count(alt.result)
    if alt.kind == "other_crop":
        name = alt.crop.label
        return Text(
            f"Sow {name.en.lower()} on the same date instead: {count.en}",
            f"Siembre {name.es.lower()} en la misma fecha: {count.es}",
        )
    weeks = abs(alt.shift_days) // 7
    earlier = alt.shift_days < 0
    return Text(
        f"Sow {weeks} weeks {'earlier' if earlier else 'later'} ({when.en}): {count.en}",
        f"Siembre {weeks} semanas {'antes' if earlier else 'después'} ({when.es}): {count.es}",
    )


def find_alternatives(
    *,
    history: DailyHistory,
    crop: CropProfile,
    plan: PlanRiskResult,
    other_crops: Sequence[CropProfile],
) -> tuple[Alternative, ...]:
    """Up to MAX_ALTERNATIVES options that failed in a smaller share of years than the plan.

    Tries the plan's crop with the sowing date shifted by SOWING_SHIFTS_DAYS, and every crop in
    `other_crops` (the MVP crops) on the plan's date. Compares failure rates, not counts, since a
    shifted date can evaluate one season fewer. Best first: lowest rate, then the same crop on
    another date before another crop (easier for the farmer), then smallest shift, then crop id.
    Options with too little history are skipped.
    """
    candidates: list[Alternative] = []
    for shift in SOWING_SHIFTS_DAYS:
        m, d = shift_date(plan.sowing_month, plan.sowing_day, shift)
        result = stress_test(history=history, crop=crop, sowing_month=m, sowing_day=d)
        candidates.append(Alternative("shift_sowing", crop, shift, result))
    for other in other_crops:
        if other.id == crop.id:
            continue
        result = stress_test(
            history=history, crop=other, sowing_month=plan.sowing_month, sowing_day=plan.sowing_day
        )
        candidates.append(Alternative("other_crop", other, 0, result))
    better = [
        a
        for a in candidates
        if not a.result.not_enough_history
        and not too_wet_for(a.result, a.crop)  # never suggest a crop that doesn't belong here
        and a.result.failure_rate < plan.failure_rate
    ]
    better.sort(
        key=lambda a: (
            a.result.failure_rate,
            a.kind != "shift_sowing",  # a date change is easier than a crop change
            abs(a.shift_days),
            a.crop.id,
        )
    )
    return tuple(better[:MAX_ALTERNATIVES])


def harvest_day(sowing_month: int, sowing_day: int, cycle_days: int) -> tuple[int, int]:
    """(month, day) of harvest for a sowing date, in a non-leap year."""
    h = sowing_date(_REFERENCE_YEAR, sowing_month, sowing_day) + timedelta(days=cycle_days)
    return h.month, h.day
