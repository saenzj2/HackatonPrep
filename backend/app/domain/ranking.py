"""Rotation ranking (v0, pending review by the agro-logic subagent / agronomist).

A rotation is one crop per season, repeated every year, so transitions are cyclic
(the last season is followed by the first one of the next year).

score = mean(crop/season scores) + rotation adjustments, clamped to 0..1
  - monoculture penalty: same crop in consecutive seasons (pest/disease build-up, soil depletion)
  - same-family penalty: different crops of the same botanical family in consecutive seasons
    (they share most pests and diseases, so the cycle is not broken)
  - legume bonus: legume after a non-legume (biological nitrogen fixation for the next crop)
A rotation is "viable" only if every crop/season score is > 0.

Each rotation carries plain-language `benefits` and `risks` for the farmer.
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
from app.domain.suitability import crop_season_fit, season_climate
from app.errors import DomainInvariantError

MONOCULTURE_PENALTY = 0.10
SAME_FAMILY_PENALTY = 0.05
LEGUME_BONUS = 0.05
# A category (climate, water, soil) at or above this is listed as a benefit.
STRONG_CATEGORY = 0.8


def _mean_category(fits: Sequence[CropSeasonFit], name: str) -> float | None:
    vals = [getattr(f.categories, name) for f in fits]
    vals = [v for v in vals if v is not None]
    return mean(vals) if vals else None


def score_rotation(fits: Sequence[CropSeasonFit]) -> RotationResult:
    n = len(fits)
    base = mean(f.score for f in fits)
    adjustment = 0.0
    benefits: list[str] = []
    risks: list[str] = []
    for i in range(n):
        prev, cur = fits[i - 1].crop, fits[i].crop  # i-1 wraps around: cyclic
        if cur.id == prev.id:
            adjustment -= MONOCULTURE_PENALTY / n
            risks.append(
                f"{cur.name} follows itself: monoculture builds up pests and depletes the soil"
            )
            continue
        if cur.family == prev.family:
            adjustment -= SAME_FAMILY_PENALTY / n
            risks.append(
                f"{cur.name} after {prev.name}: same family ({cur.family}), "
                "the pest and disease cycle is not broken"
            )
        else:
            benefits.append(
                f"{prev.name} ({prev.family}) → {cur.name} ({cur.family}): "
                "family change breaks pest and disease cycles"
            )
        if cur.is_legume and not prev.is_legume:
            adjustment += LEGUME_BONUS / n
            benefits.append(
                f"{cur.name} (legume) after {prev.name}: fixes nitrogen for the next crop"
            )
    for f in fits:
        risks.extend(f.risks)
    breakdown = CategoryScores(
        climate=_mean_category(fits, "climate"),
        water=_mean_category(fits, "water"),
        soil=_mean_category(fits, "soil"),
    )
    for name, value in vars(breakdown).items():
        if value is not None and value >= STRONG_CATEGORY:
            benefits.append(f"Strong {name} fit across the year ({value:.2f})")
    return RotationResult(
        sequence=tuple(fits),
        score=min(1.0, max(0.0, base + adjustment)),
        breakdown=breakdown,
        viable=all(f.score > 0 for f in fits),
        benefits=tuple(dict.fromkeys(benefits)),  # dedupe, keep order
        risks=tuple(dict.fromkeys(risks)),
    )


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


def explain(r: RotationResult) -> str:
    """One plain-language sentence for the farmer."""
    names = " → ".join(f"{f.crop.name} ({f.season.name})" for f in r.sequence)
    if not r.viable:
        return f"{names}: not recommended, at least one crop is outside its limits in its season."
    cats: dict[str, float] = {k: v for k, v in vars(r.breakdown).items() if v is not None}
    best = max(cats, key=lambda k: cats[k])
    worst = min(cats, key=lambda k: cats[k])
    if best == worst or cats[best] - cats[worst] < 0.05:
        return f"{names}: balanced fit across {', '.join(cats)} (score {r.score:.2f})."
    return (
        f"{names}: strongest on {best} ({cats[best]:.2f}), "
        f"weakest on {worst} ({cats[worst]:.2f}); overall {r.score:.2f}."
    )
