"""Actions and alternatives for a risky plan (app/domain/plan_advice.py), on toy weather."""

from datetime import date
from typing import get_args

import pandas as pd
import pytest

from app import services
from app.api import schemas as s
from app.domain.models import Range
from app.domain.plan_advice import (
    ACTIONS,
    INSURANCE_ACTION,
    MAX_ALTERNATIVES,
    actions_for,
    find_alternatives,
    harvest_day,
    outcome_count,
    plan_summary,
    shift_date,
    warm_nights_note,
)
from app.domain.plan_risk import Cause, CauseSummary, Finding, stress_test, too_wet_for
from app.domain.text import Text
from tests.test_plan_risk import Weather, toy_crop

YEARS = 12  # seasons sown every Mar 1, 2001..2012: enough history (MIN_VALID_SEASONS = 10)


def summary(cause: Cause, severity: str) -> CauseSummary:
    finding = Finding(cause=cause, severity=severity, badness=1.0, evidence=Text("x", "y"))
    return CauseSummary(
        cause=cause, severity=severity, years=(2001,), worst_year=2001, worst=finding
    )


def history_years() -> Weather:
    """Daily weather from 2001-01-01 to cover Mar 1 ± 28 days sowings for YEARS seasons."""
    return Weather(start=date(2001, 1, 1), days=(date(2001 + YEARS, 1, 1) - date(2001, 1, 1)).days)


# ---------------------------------------------------------------- actions
@pytest.mark.parametrize("cause", sorted(ACTIONS))
def test_every_cause_has_two_or_three_bilingual_actions(cause):
    actions = ACTIONS[cause]
    assert 2 <= len(actions) <= 3
    for a in actions:
        assert a.en.strip()
        assert a.es.strip()
        assert a.en != a.es


def test_every_cause_the_engine_produces_has_actions():
    assert set(get_args(Cause)) == set(ACTIONS)


def test_crop_specific_action_comes_first():
    actions = actions_for(summary("harvest_wet", "stress"), toy_crop(id="maize"))
    # "La dobla": the stalk is bent below the ear, not the ear itself (Munguía 1995).
    assert actions[0].es == (
        "Haga la dobla: doble la caña debajo de la mazorca para que quede hacia abajo y escurra "
        "la lluvia"
    )
    assert actions[1:] == ACTIONS["harvest_wet"]


@pytest.mark.parametrize(("severity", "insured"), [("fail", True), ("stress", False)])
def test_insurance_is_suggested_only_for_causes_that_failed_a_year(severity, insured):
    actions = actions_for(summary("flowering_dry_spell", severity), toy_crop())
    assert (actions[-1] == INSURANCE_ACTION) is insured


def test_insurance_action_only_asks_and_uses_the_current_product_name():
    assert INSURANCE_ACTION.en.startswith("Ask")
    assert (
        INSURANCE_ACTION.es
        == "Pregunte al INS si el Seguro Agrícola cubre este riesgo en su cultivo"
    )
    assert "whether" in INSURANCE_ACTION.en  # asks, never claims coverage


# ---------------------------------------------------------------- dates
@pytest.mark.parametrize(
    ("month", "day", "shift", "expected"),
    [
        (3, 1, -14, (2, 15)),
        (1, 5, -14, (12, 22)),  # wraps back over the new year
        (12, 20, 14, (1, 3)),  # wraps forward
        (2, 29, 0, (2, 28)),  # Feb 29 counts as Feb 28
    ],
)
def test_shift_date(month, day, shift, expected):
    assert shift_date(month, day, shift) == expected


def test_harvest_day_crosses_the_year():
    assert harvest_day(12, 1, 110) == (3, 21)


# ---------------------------------------------------------------- alternatives
def dry_start_every_year(w: Weather) -> Weather:
    """Mar 1–20 nearly dry every year: Mar 1 sowings fail late_dry_start (4 mm in 20 days).
    Sowings 2+ weeks away see at most 6 of those dry days: fine."""
    for year in range(2001, 2001 + YEARS):
        w.set("rain", 0, 19, 0.2, sown=date(year, 3, 1))
    return w


def run_plan(w: Weather, crop=None):
    crop = crop or toy_crop()
    plan = stress_test(history=w.history(), crop=crop, sowing_month=3, sowing_day=1)
    return crop, plan


def test_alternatives_are_better_dates_smallest_shift_first():
    w = dry_start_every_year(history_years())
    crop, plan = run_plan(w)
    assert plan.failure_rate == 1.0
    alts = find_alternatives(history=w.history(), crop=crop, plan=plan, other_crops=[crop])
    assert [a.shift_days for a in alts] == [-14, 14, -28]  # ties on rate: smaller shift first
    assert len(alts) == MAX_ALTERNATIVES
    assert all(a.result.failure_rate < plan.failure_rate for a in alts)


def test_alternative_label_for_a_shift():
    w = dry_start_every_year(history_years())
    crop, plan = run_plan(w)
    first = find_alternatives(history=w.history(), crop=crop, plan=plan, other_crops=[])[0]
    assert first.label.en == (
        "Sow 2 weeks earlier (February 15): would not have failed in any of the 12 years"
    )
    assert first.label.es == (
        "Siembre 2 semanas antes (15 de febrero): no habría fallado en ninguno de los 12 años"
    )


HARDY = toy_crop(
    id="hardy", name="Hardy", name_es="Resistente", temperature_c=Range(10, 18, 33, 35)
)


def hot_every_year(w: Weather, first: int, last: int) -> Weather:
    """31 °C on days first..last after Mar 1 every year: too hot for the toy crop (limit 30 °C),
    fine for HARDY (limit 35 °C)."""
    for year in range(2001, 2001 + YEARS):
        w.set("tmax", first, last, 31.0, sown=date(year, 3, 1))
    return w


def test_another_crop_on_the_same_date_can_be_an_alternative():
    # Hot from day 17 to 95 after Mar 1: every shift of ±2 or ±4 weeks still flowers in the heat.
    w = hot_every_year(history_years(), 17, 95)
    crop, plan = run_plan(w)
    alts = find_alternatives(history=w.history(), crop=crop, plan=plan, other_crops=[crop, HARDY])
    assert [(a.kind, a.crop.id, a.shift_days) for a in alts] == [("other_crop", "hardy", 0)]
    assert alts[0].label.es == (
        "Siembre resistente en la misma fecha: no habría fallado en ninguno de los 12 años"
    )


def test_a_date_change_ranks_before_a_crop_change_at_the_same_rate():
    # Hot only on days 45–54: shifting the date avoids it as well as switching crops does.
    w = hot_every_year(history_years(), 45, 54)
    crop, plan = run_plan(w)
    alts = find_alternatives(history=w.history(), crop=crop, plan=plan, other_crops=[crop, HARDY])
    assert [a.kind for a in alts] == ["shift_sowing"] * MAX_ALTERNATIVES


def test_no_alternatives_when_the_plan_never_fails():
    w = history_years()
    crop, plan = run_plan(w)
    assert plan.failed_years == 0
    assert find_alternatives(history=w.history(), crop=crop, plan=plan, other_crops=[crop]) == ()


def test_options_without_enough_history_are_skipped():
    w = Weather(start=date(2001, 1, 1), days=400)  # one season only
    w.set("rain", 0, 19, 0.2, sown=date(2001, 3, 1))
    crop, plan = run_plan(w)
    assert find_alternatives(history=w.history(), crop=crop, plan=plan, other_crops=[]) == ()


@pytest.mark.parametrize(
    ("failed", "expected_es"),
    [(0, "no habría fallado en ninguno de los 12 años"), (12, "habría fallado en 12 de 12 años")],
)
def test_outcome_count_wording(failed, expected_es):
    w = history_years()
    if failed:
        dry_start_every_year(w)
    _, plan = run_plan(w)
    assert outcome_count(plan).es == expected_es


# ---------------------------------------------------------------- crops that don't belong here
# Toy weather: 5 mm a day = 500 mm per 100-day cycle. A crop with abs_max 400 is too wet here.
SOGGY = toy_crop(id="soggy", name="Sorghum", name_es="Sorgo", rainfall_mm=Range(100, 200, 300, 400))


def test_typical_cycle_rain_is_the_median_season():
    _, plan = run_plan(history_years())
    assert plan.typical_cycle_rain_mm == pytest.approx(500.0)


@pytest.mark.parametrize(("abs_max", "too_wet"), [(500, False), (499, True)])
def test_too_wet_when_a_typical_season_exceeds_the_crop_limit(abs_max, too_wet):
    crop = toy_crop(rainfall_mm=Range(100, 200, 300, abs_max))
    _, plan = run_plan(history_years(), crop)
    assert too_wet_for(plan, crop) is too_wet


def test_summary_says_too_wet_even_without_failures():
    _, plan = run_plan(history_years(), SOGGY)
    assert plan.failed_years == 0
    text = plan_summary(plan, SOGGY)
    assert text.en == (
        "Too much rain for sorghum here: a typical season gets about 500 mm over the cycle, "
        "far above the 400 mm upper limit FAO gives for sorghum. Not recommended here."
    )
    assert text.es == (
        "Demasiada lluvia para el sorgo aquí: en un ciclo típico caen unos 500 mm, muy por "
        "encima del límite de 400 mm que da la FAO para el sorgo. No se recomienda en este lugar."
    )


def test_a_crop_too_wet_for_the_place_is_never_an_alternative():
    w = hot_every_year(history_years(), 17, 95)  # only another crop could help
    crop, plan = run_plan(w)
    soggy_hardy = toy_crop(
        id="soggy_hardy",
        temperature_c=Range(10, 18, 33, 35),
        rainfall_mm=Range(100, 200, 300, 400),
    )
    alts = find_alternatives(history=w.history(), crop=crop, plan=plan, other_crops=[soggy_hardy])
    assert alts == ()


@pytest.mark.parametrize(
    ("failed", "expected_en"),
    [
        (0, "Would not have failed in any of the 12 years, and no weather problems were found."),
        (12, "Would have failed in 12 of 12 years, mostly because of a dry start after sowing."),
    ],
)
def test_plan_summary_wording(failed, expected_en):
    w = history_years()
    if failed:
        dry_start_every_year(w)
    crop, plan = run_plan(w)
    assert plan_summary(plan, crop).en == expected_en


def test_plan_summary_names_the_main_stress_when_nothing_failed():
    w = history_years()
    for year in (2003, 2006):  # 28 mm in the first 20 days: stress only
        w.set("rain", 0, 19, 1.4, sown=date(year, 3, 1))
    crop, plan = run_plan(w)
    assert plan_summary(plan, crop).es == (
        "No habría fallado en ninguno de los 12 años; ojo con un inicio seco después de la "
        "siembra (2 de 12 años)."
    )


def test_not_enough_history_summary():
    crop, plan = run_plan(Weather(start=date(2001, 1, 1), days=400))
    assert plan_summary(plan, crop).en == "Not enough complete seasons to judge this plan (only 1)"


# ---------------------------------------------------------------- warm nights (note, not a cause)
def warm_nights_every_year(w: Weather, nights: int) -> Weather:
    """`nights` nights at 21 °C at the start of flowering (days 35.. for beans), every year."""
    for year in range(2001, 2001 + YEARS):
        w.set("tmin", 35, 35 + nights - 1, 21.0, sown=date(year, 3, 1))
    return w


@pytest.mark.parametrize(("nights", "noted"), [(4, False), (5, True)])
def test_warm_nights_note_needs_enough_nights_in_a_typical_season(nights, noted):
    beans = toy_crop(id="beans", name="Common bean", name_es="Frijol")
    w = warm_nights_every_year(history_years(), nights)
    _, plan = run_plan(w, beans)
    assert (warm_nights_note(plan, beans) is not None) is noted


def test_warm_nights_never_count_as_a_failure():
    beans = toy_crop(id="beans", name="Common bean", name_es="Frijol")
    _, plan = run_plan(warm_nights_every_year(history_years(), 25), beans)
    assert plan.failed_years == 0
    assert plan.cause_summaries() == ()


def test_warm_nights_note_only_for_beans_and_cowpea():
    maize = toy_crop(id="maize")
    _, plan = run_plan(warm_nights_every_year(history_years(), 20), maize)
    assert warm_nights_note(plan, maize) is None


def test_warm_nights_note_text():
    beans = toy_crop(id="beans", name="Common bean", name_es="Frijol")
    _, plan = run_plan(warm_nights_every_year(history_years(), 25), beans)
    note = warm_nights_note(plan, beans)
    assert note.es == (
        "Frijol, siembra del 1 de marzo: en la floración, aquí las noches casi siempre pasan de "
        "20 °C (25 de 25 noches en un año típico). Las noches calientes hacen que la planta pegue "
        "menos vainas. Es normal en este lugar, así que no se cuenta como año malo; consulte en "
        "la agencia de extensión del MAG por variedades que aguanten el calor"
    )


def test_not_enough_history_gap_is_listed_once_per_planting():
    """The same crop and date twice (allowed, up to 4 plantings) → one data gap, not two."""
    history = Weather(days=50).history()
    crop = toy_crop()
    plan = stress_test(history=history, crop=crop, sowing_month=3, sowing_day=1)
    assert plan.not_enough_history
    years = s.YearsEvaluated(first=0, last=0, count=0)
    df = pd.DataFrame({"rainfall_mm": [], "rainfall_merra2_mm": []})  # no rain-source gap
    gaps = services._plan_risk_data_gaps(df, years, [(crop, plan), (crop, plan)], enso_gaps=[])
    too_few = [g for g in gaps if "too few to judge" in g.en]
    assert len(too_few) == 1
