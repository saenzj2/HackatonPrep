"""Rotation rules (#25): verdict and one-line reason for any two consecutive crops.

Toy crops only (built from tests/test_domain.crop), so expected verdicts are obvious by hand.
"""

import itertools
from dataclasses import replace

import pytest

from app.domain.models import CropProfile
from app.domain.rotation_rules import (
    FUNGI_BREAK_PENALTY,
    HEAVY_AFTER_HEAVY_PENALTY,
    LEGUME_BONUS,
    MAX_PAIR_PENALTY,
    MONOCULTURE_PENALTY,
    SAME_FAMILY_PENALTY,
    judge_transition,
)
from app.errors import DomainInvariantError
from tests.test_domain import crop, rank

HEAVY = 1.0  # nitrogen_demand → "high"
LIGHT = 0.33  # nitrogen_demand → "low"


def plant(
    id_: str,
    *,
    family: str = "Poaceae",
    legume: bool = False,
    nitrogen: float = 0.67,
    fungi: float = 0.67,
) -> CropProfile:
    return replace(
        crop(id_, legume=legume, family=family),
        nitrogen_demand=nitrogen,
        mycorrhizal_affinity=fungi,
    )


MAIZE = plant("maize", nitrogen=HEAVY)
RICE = plant("rice", nitrogen=HEAVY)
SORGHUM = plant("sorghum")
BEANS = plant("beans", family="Fabaceae", legume=True, nitrogen=LIGHT)
SQUASH = plant("squash", family="Cucurbitaceae")
AMARANTH = plant("amaranth", family="Amaranthaceae", fungi=0.0)
DEPENDENT = plant("dependent", family="Solanaceae", fungi=1.0)


def rules(prev, cur):
    return [h.rule for h in judge_transition(prev, cur).hits]


# ---------------------------------------------------------------- one test per rule
def test_monoculture_is_discouraged_and_skips_other_rules():
    j = judge_transition(MAIZE, MAIZE)  # also a heavy feeder after itself
    assert j.verdict == "discouraged"
    assert rules(MAIZE, MAIZE) == ["monoculture"]
    assert j.adjustment == pytest.approx(-MONOCULTURE_PENALTY)
    assert "monoculture" in j.hits[0].reason.en


def test_same_family_is_discouraged():
    j = judge_transition(SORGHUM, MAIZE)
    assert j.verdict == "discouraged"
    assert rules(SORGHUM, MAIZE) == ["same_family"]
    assert j.adjustment == pytest.approx(-SAME_FAMILY_PENALTY)
    assert "same grass family" in j.hits[0].reason.en


def test_family_change_alone_is_allowed_without_score_change():
    j = judge_transition(SORGHUM, SQUASH)
    assert j.verdict == "allowed"
    assert rules(SORGHUM, SQUASH) == ["family_change"]
    assert j.adjustment == 0


def test_legume_after_heavy_feeder_is_favoured_with_stronger_reason():
    j = judge_transition(MAIZE, BEANS)
    assert j.verdict == "favoured"
    assert rules(MAIZE, BEANS) == ["family_change", "legume_restores_nitrogen"]
    assert j.adjustment == pytest.approx(LEGUME_BONUS)
    assert "which needs a lot of nitrogen" in j.hits[-1].reason.en


def test_legume_after_other_non_legume_is_favoured_with_plain_reason():
    j = judge_transition(SORGHUM, BEANS)
    assert j.verdict == "favoured"
    assert j.adjustment == pytest.approx(LEGUME_BONUS)
    assert "which needs a lot of nitrogen" not in j.hits[-1].reason.en
    assert "nitrogen from the air" in j.hits[-1].reason.en


def test_legume_after_legume_gets_no_bonus():
    other_legume = plant("cowpea", family="Fabaceae", legume=True, nitrogen=LIGHT)
    assert "legume_restores_nitrogen" not in rules(BEANS, other_legume)


def test_non_legume_after_legume_is_allowed():
    assert judge_transition(BEANS, MAIZE).verdict == "allowed"


def test_heavy_after_heavy_is_discouraged():
    heavy_squash = replace(SQUASH, nitrogen_demand=HEAVY)  # different family: only this rule
    j = judge_transition(MAIZE, heavy_squash)
    assert j.verdict == "discouraged"
    assert rules(MAIZE, heavy_squash) == ["family_change", "heavy_after_heavy"]
    assert j.adjustment == pytest.approx(-HEAVY_AFTER_HEAVY_PENALTY)
    assert "both need a lot of nitrogen" in j.hits[-1].reason.en


def test_stacked_risks_are_capped_below_monoculture():
    """Same family + both heavy feeders: two reasons, but still better than repeating the crop."""
    j = judge_transition(RICE, MAIZE)
    assert rules(RICE, MAIZE) == ["same_family", "heavy_after_heavy"]
    assert SAME_FAMILY_PENALTY + HEAVY_AFTER_HEAVY_PENALTY > MAX_PAIR_PENALTY  # the cap applies
    assert j.adjustment == pytest.approx(-MAX_PAIR_PENALTY)


def test_medium_nitrogen_demand_is_not_a_heavy_feeder():
    assert "heavy_after_heavy" not in rules(MAIZE, replace(SQUASH, nitrogen_demand=0.67))


def test_fungi_break_is_discouraged():
    j = judge_transition(AMARANTH, DEPENDENT)
    assert j.verdict == "discouraged"
    assert rules(AMARANTH, DEPENDENT) == ["family_change", "fungi_break"]
    assert j.adjustment == pytest.approx(-FUNGI_BREAK_PENALTY)
    assert "doesn't feed the helpful soil fungi" in j.hits[-1].reason.en


@pytest.mark.parametrize(
    ("prev", "cur"),
    [
        (DEPENDENT, AMARANTH),  # wrong order: the fungi break after the dependent crop
        (replace(AMARANTH, mycorrhizal_affinity=0.33), DEPENDENT),  # low, not a non-host
        (AMARANTH, replace(DEPENDENT, mycorrhizal_affinity=0.67)),  # medium, not dependent
    ],
)
def test_fungi_break_needs_non_host_then_dependent(prev, cur):
    assert "fungi_break" not in rules(prev, cur)


# ---------------------------------------------------------------- combining
def test_risk_wins_over_benefit_and_both_reasons_are_kept():
    """A legume after a heavy feeder that is also a non-host, before a fungi-dependent legume."""
    non_host_heavy = plant("kale", family="Brassicaceae", nitrogen=HEAVY, fungi=0.0)
    dependent_legume = plant("soy", family="Fabaceae", legume=True, nitrogen=LIGHT, fungi=1.0)
    j = judge_transition(non_host_heavy, dependent_legume)
    assert j.verdict == "discouraged"
    assert {"legume_restores_nitrogen", "fungi_break"} <= set(
        rules(non_host_heavy, dependent_legume)
    )
    assert j.adjustment == pytest.approx(LEGUME_BONUS - FUNGI_BREAK_PENALTY)


TOY_CROPS = [MAIZE, RICE, SORGHUM, BEANS, SQUASH, AMARANTH, DEPENDENT]


@pytest.mark.parametrize(("prev", "cur"), list(itertools.product(TOY_CROPS, repeat=2)))
def test_every_pair_gets_a_verdict_and_a_reason(prev, cur):
    j = judge_transition(prev, cur)
    assert j.verdict in {"favoured", "allowed", "discouraged"}
    assert j.hits
    assert all(h.reason.en and h.reason.es for h in j.hits)
    assert all(h.reason.es != h.reason.en for h in j.hits)  # really translated
    if prev.id != cur.id:  # changing crops always beats repeating one (agro-logic review)
        assert j.adjustment > -MONOCULTURE_PENALTY


# ---------------------------------------------------------------- in the ranking
def test_ranking_judges_the_wrap_around_transition():
    """beans → maize only gets the legume reason from the wrap-around (maize → beans next year)."""
    results = {tuple(f.crop.id for f in r.sequence): r for r in rank([MAIZE, BEANS], top_n=None)}
    assert any(
        "which needs a lot of nitrogen" in b.en for b in results[("beans", "maize")].benefits
    )


def test_two_heavy_feeders_rank_below_a_light_one():
    scores = {
        tuple(f.crop.id for f in r.sequence): r.score
        for r in rank([MAIZE, RICE, SORGHUM], top_n=None)
    }
    assert scores[("maize", "rice")] < scores[("maize", "sorghum")]


def test_rules_never_make_a_rotation_non_viable():
    results = rank([MAIZE], top_n=None)  # only monoculture possible
    assert results[0].viable


# ------------------------------------------------ Spanish grammatical gender
def test_article_follows_the_crop_gender():
    maize = replace(plant("maize"), name="Maize", name_es="Maíz")
    cassava = replace(plant("cassava"), name="Cassava", name_es="Yuca", gender_es="f")
    assert (maize.the_es, maize.of_the_es) == ("el maíz", "del maíz")
    assert (cassava.the_es, cassava.of_the_es) == ("la yuca", "de la yuca")


def test_feminine_crop_gets_la_and_de_la_in_spanish_reasons():
    yuca = replace(plant("cassava"), name="Cassava", name_es="Yuca", gender_es="f")
    verdict = judge_transition(yuca, yuca)  # monoculture
    (hit,) = verdict.hits
    assert "enfermedades de la yuca se acumulan" in hit.reason.es
    assert "del yuca" not in hit.reason.es


def test_feminine_legume_reason_uses_la():
    bean = replace(
        plant("tarwi", legume=True, family="Fabaceae"),
        name="Tarwi",
        name_es="Chocho",
        gender_es="f",
    )
    verdict = judge_transition(plant("maize", nitrogen=HEAVY), bean)
    assert any("la chocho (leguminosa)" in h.reason.es for h in verdict.hits)


def test_unknown_gender_is_rejected():
    with pytest.raises(DomainInvariantError, match="gender_es"):
        replace(plant("maize"), gender_es="x")
