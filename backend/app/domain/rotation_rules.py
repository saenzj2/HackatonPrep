"""Rotation rules: judge one crop following another (T3.3, #25).

Each rule looks at two consecutive crops and either stays quiet or returns one plain-language reason
with a score adjustment. judge_transition() runs every rule and combines them into a verdict:

  rule                      fires when                                    verdict      score
  monoculture               same crop again (skips the other rules)       discouraged  -0.10
  same_family               different crops, same botanical family        discouraged  -0.05
  family_change             crops of different families                   allowed       0
  legume_restores_nitrogen  a legume after a non-legume                   favoured     +0.05
  heavy_after_heavy         two heavy feeders (high N demand) in a row    discouraged  -0.05
  fungi_break               non-host before a crop that depends on fungi  discouraged  -0.05

Verdict: any risk → discouraged; else a benefit that moves the score → favoured; else allowed.
For two different crops the summed penalties are capped at MAX_PAIR_PENALTY (< monoculture).
"Heavy feeder" and "depends on fungi" mean the trait's API word is "high" (level_for), so the rules
and the API agree. Score values are placeholders: change them only with a docs/decisions.md entry.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from app.domain.models import CropProfile, level_for
from app.domain.text import Text, family

MONOCULTURE_PENALTY = 0.10  # placeholder (decisions.md 2026-11-06)
SAME_FAMILY_PENALTY = 0.05  # placeholder, half of monoculture (decisions.md 2026-11-14)
LEGUME_BONUS = 0.05  # placeholder (decisions.md 2026-11-06)
HEAVY_AFTER_HEAVY_PENALTY = 0.05  # placeholder, same weight as same family (#25)
FUNGI_BREAK_PENALTY = 0.05  # placeholder, same weight as same family (#25)
# Changing crops always beats repeating one: risks for two different crops add up to at most this.
# Without it, same family + two heavy feeders tied with monoculture (agro-logic review, #25).
MAX_PAIR_PENALTY = MONOCULTURE_PENALTY - 0.025

Verdict = Literal["favoured", "allowed", "discouraged"]
Effect = Literal["benefit", "risk"]


@dataclass(frozen=True)
class RuleHit:
    rule: str
    effect: Effect
    reason: Text  # one line for the farmer, English and Spanish
    adjustment: float  # score change for this transition, before dividing by the number of seasons


@dataclass(frozen=True)
class TransitionJudgement:
    prev: CropProfile
    cur: CropProfile
    verdict: Verdict
    hits: tuple[RuleHit, ...]  # never empty: every transition has at least one reason

    @property
    def adjustment(self) -> float:
        total = sum(h.adjustment for h in self.hits)
        if self.cur.id == self.prev.id:
            return total
        return max(total, -MAX_PAIR_PENALTY)


def _is_heavy_feeder(c: CropProfile) -> bool:
    return level_for(c.nitrogen_demand) == "high"


def _same_family(prev: CropProfile, cur: CropProfile) -> RuleHit | None:
    if cur.family != prev.family:
        return None
    a, bl, fam = cur.label, prev.label.lower(), family(cur.family)
    return RuleHit(
        "same_family",
        "risk",
        Text(
            f"{a.en} after {bl.en}: same {fam.en}, they share some pests and diseases, so the "
            "break is weaker",
            f"{a.es} después de {bl.es}: misma {fam.es}, comparten plagas y enfermedades, así que "
            "el descanso sirve menos",
        ),
        -SAME_FAMILY_PENALTY,
    )


def _family_change(prev: CropProfile, cur: CropProfile) -> RuleHit | None:
    if cur.family == prev.family:
        return None
    a, bl = cur.label, prev.label.lower()
    fa, fb = family(cur.family), family(prev.family)
    return RuleHit(
        "family_change",
        "benefit",
        Text(
            f"{a.en} after {bl.en}: changing from the {fb.en} to the {fa.en} helps cut pest and "
            "disease cycles",
            f"{a.es} después de {bl.es}: pasar de la {fb.es} a la {fa.es} ayuda a cortar el ciclo "
            "de plagas y enfermedades",
        ),
        0.0,
    )


def _legume_restores_nitrogen(prev: CropProfile, cur: CropProfile) -> RuleHit | None:
    if not cur.is_legume or prev.is_legume:
        return None
    a, al, bl = cur.label, cur.label.lower(), prev.label.lower()
    # Beans take roughly 40 % of their nitrogen from the air (Reinprecht et al. 2020) and most of
    # it leaves with the grain: say "part" and "a little", never "most" or "less fertilizer".
    if _is_heavy_feeder(prev):
        reason = Text(
            f"{a.en} after {bl.en}, which needs a lot of nitrogen: {al.en} (bean family) takes "
            "part of its nitrogen from the air, so it draws less from the soil; its crop residues "
            "add a little for the next crop",
            f"{a.es} después de {bl.es}, que pide mucho nitrógeno: {cur.the_es} (leguminosa) "
            "toma parte de su nitrógeno del aire y gasta menos del suelo; los rastrojos dejan un "
            "poco para el siguiente cultivo",
        )
    else:
        reason = Text(
            f"{a.en} after {bl.en}: {al.en} (bean family) takes part of its nitrogen from the air, "
            "so it draws less from the soil; its crop residues add a little for the next crop",
            f"{a.es} después de {bl.es}: {cur.the_es} (leguminosa) toma parte de su nitrógeno "
            "del aire y gasta menos del suelo; los rastrojos dejan un poco para el siguiente "
            "cultivo",
        )
    return RuleHit("legume_restores_nitrogen", "benefit", reason, LEGUME_BONUS)


def _heavy_after_heavy(prev: CropProfile, cur: CropProfile) -> RuleHit | None:
    if not (_is_heavy_feeder(prev) and _is_heavy_feeder(cur)):
        return None
    a, al, bl = cur.label, cur.label.lower(), prev.label.lower()
    return RuleHit(
        "heavy_after_heavy",
        "risk",
        Text(
            f"{a.en} after {bl.en}: both need a lot of nitrogen, so expect to fertilize more "
            f"for {al.en}",
            f"{a.es} después de {bl.es}: los dos piden mucho nitrógeno; cuente con abonar más "
            f"{cur.the_es}",
        ),
        -HEAVY_AFTER_HEAVY_PENALTY,
    )


def _fungi_break(prev: CropProfile, cur: CropProfile) -> RuleHit | None:
    if level_for(prev.mycorrhizal_affinity) != "none":
        return None
    if level_for(cur.mycorrhizal_affinity) != "high":
        return None
    a, al, bl = cur.label, cur.label.lower(), prev.label.lower()
    return RuleHit(
        "fungi_break",
        "risk",
        Text(
            f"{a.en} after {bl.en}: {bl.en} doesn't feed the helpful soil fungi (mycorrhizae), so "
            f"fewer are left for {al.en}, which relies on them to take up phosphorus",
            f"{a.es} después de {bl.es}: {prev.the_es} no alimenta los hongos buenos del suelo "
            f"(micorrizas), y {cur.the_es} los necesita para aprovechar el fósforo",
        ),
        -FUNGI_BREAK_PENALTY,
    )


# Every rule for two different crops. Add a rule: write the function, then list it here.
RULES: tuple[Callable[[CropProfile, CropProfile], RuleHit | None], ...] = (
    _same_family,
    _family_change,
    _legume_restores_nitrogen,
    _heavy_after_heavy,
    _fungi_break,
)


def _verdict(hits: tuple[RuleHit, ...]) -> Verdict:
    if any(h.effect == "risk" for h in hits):
        return "discouraged"
    if any(h.adjustment > 0 for h in hits):
        return "favoured"
    return "allowed"


def judge_transition(prev: CropProfile, cur: CropProfile) -> TransitionJudgement:
    """Verdict and reasons for `cur` planted in the season right after `prev`."""
    if cur.id == prev.id:
        c = cur.label.lower()
        # Monoculture says it all; stacking heavy_after_heavy etc. would double-count.
        hits: tuple[RuleHit, ...] = (
            RuleHit(
                "monoculture",
                "risk",
                Text(
                    f"{cur.label.en} after {c.en} (monoculture): pests and diseases of "
                    f"{c.en} build up season after season",
                    f"{cur.label.es} después de {c.es} (monocultivo): las plagas y "
                    f"enfermedades {cur.of_the_es} se acumulan época tras época",
                ),
                -MONOCULTURE_PENALTY,
            ),
        )
    else:
        hits = tuple(hit for rule in RULES if (hit := rule(prev, cur)) is not None)
    return TransitionJudgement(prev=prev, cur=cur, verdict=_verdict(hits), hits=hits)
