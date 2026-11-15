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
    reason: str  # one line for the farmer
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
    return RuleHit(
        "same_family",
        "risk",
        f"{cur.name} after {prev.name}: same family ({cur.family}), "
        "they share some pests and diseases, so the break is weaker",
        -SAME_FAMILY_PENALTY,
    )


def _family_change(prev: CropProfile, cur: CropProfile) -> RuleHit | None:
    if cur.family == prev.family:
        return None
    return RuleHit(
        "family_change",
        "benefit",
        f"{prev.name} ({prev.family}) → {cur.name} ({cur.family}): "
        "family change helps break pest and disease cycles",
        0.0,
    )


def _legume_restores_nitrogen(prev: CropProfile, cur: CropProfile) -> RuleHit | None:
    if not cur.is_legume or prev.is_legume:
        return None
    if _is_heavy_feeder(prev):
        reason = (
            f"{cur.name} (legume) after {prev.name}, a heavy feeder: it takes most of its "
            "nitrogen from the air instead of the soil, "
            "and its residues leave a little for the next crop"
        )
    else:
        reason = (
            f"{cur.name} (legume) after {prev.name}: it takes nitrogen from the air, "
            "so the next crop may need less fertilizer"
        )
    return RuleHit("legume_restores_nitrogen", "benefit", reason, LEGUME_BONUS)


def _heavy_after_heavy(prev: CropProfile, cur: CropProfile) -> RuleHit | None:
    if not (_is_heavy_feeder(prev) and _is_heavy_feeder(cur)):
        return None
    return RuleHit(
        "heavy_after_heavy",
        "risk",
        f"{cur.name} after {prev.name}: both need a lot of nitrogen, "
        f"so expect to fertilize more for {cur.name}",
        -HEAVY_AFTER_HEAVY_PENALTY,
    )


def _fungi_break(prev: CropProfile, cur: CropProfile) -> RuleHit | None:
    if level_for(prev.mycorrhizal_affinity) != "none":
        return None
    if level_for(cur.mycorrhizal_affinity) != "high":
        return None
    return RuleHit(
        "fungi_break",
        "risk",
        f"{prev.name} before {cur.name}: {prev.name} doesn't feed the soil fungi (mycorrhizae), "
        f"so fewer are left for {cur.name}, which relies on them to take up phosphorus",
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
        # Monoculture says it all; stacking heavy_after_heavy etc. would double-count.
        hits: tuple[RuleHit, ...] = (
            RuleHit(
                "monoculture",
                "risk",
                f"{cur.name} follows itself (monoculture): pests and diseases of {cur.name} "
                "build up season after season",
                -MONOCULTURE_PENALTY,
            ),
        )
    else:
        hits = tuple(hit for rule in RULES if (hit := rule(prev, cur)) is not None)
    return TransitionJudgement(prev=prev, cur=cur, verdict=_verdict(hits), hits=hits)
