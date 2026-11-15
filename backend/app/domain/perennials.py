"""Suitability of a permanent crop (cacao, coffee, pineapple, banana) at a point, over the year.

Permanent crops stay in the field for years: there is no season, sowing date or rotation, so the
season scoring in suitability.py does not apply. Each crop is scored once against the 12-month
climate with the same trapezoids as annual crops:

- temperature: mean annual temperature vs the crop's range;
- rainfall:    annual total vs the crop's range (EcoCrop ranges are annual, so they fit directly);
- heat:        hottest month's mean daily max vs the crop's absolute max (as for annuals);
- frost:       mean daily min of the coldest month (same generic range as annuals);
- soil_ph:     as for annuals.

The crop's score is its MOST LIMITING variable (the minimum), as in the original EcoCrop model
(Hijmans, R package Recocrop: "law of the minimum"), not the priority-weighted mean used for
rotations: a mean let a lowland too hot for arabica coffee (heat 0.14 at Liberia) still score
0.91. So the farmer's priorities do not change this score; the category breakdown is still
reported.

Soil moisture is not scored (its generic range is for annual crops in their season). The dry
season is reported, never scored: EcoCrop has no dry-season tolerance per crop.
Pure, stdlib only. Thresholds are placeholders pending the agro-logic review.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from statistics import mean
from typing import Literal

from app.domain.models import (
    CategoryScores,
    MonthlyClimate,
    PerennialCropProfile,
    Range,
    SoilConditions,
)
from app.domain.suitability import (
    CATEGORY_OF,
    FROST_RANGE,
    HEAT_MARGIN_C,
    MARGINAL_SCORE,
    trapezoid,
)
from app.domain.text import MONTHS_ABBR_EN, MONTHS_ABBR_ES, Text, num

Suitability = Literal["good", "fair", "poor", "unsuitable"]

# Variables a permanent crop is scored on; others in mvp.yaml (soil_moisture) are skipped.
PERENNIAL_VARIABLES = ("temperature", "rainfall", "heat", "frost", "soil_ph")
# Placeholder: a month with less rain than this counts as dry (the 60 mm tropical-dry bar used in
# the Köppen classification).
DRY_MONTH_MM = 60.0
# Placeholder: this many dry months or more gets a note that young plants need water then.
LONG_DRY_SEASON_MONTHS = 4
# Placeholder: score from which a crop is "good" here; "fair" from MARGINAL_SCORE (0.5).
GOOD_SCORE = 0.8
_NO_LOWER_LIMIT_C = -100.0  # heat has no lower limit; the trapezoid needs one


@dataclass(frozen=True)
class YearClimate:
    """The whole year at a point, from monthly normals."""

    annual_rainfall_mm: float
    temperature_c: float  # mean of the 12 monthly means
    hottest_month_max_c: float  # highest monthly mean of the daily max
    coldest_month_min_c: float  # lowest monthly mean of the daily min
    dry_months: tuple[int, ...]  # 1..12, months with less than DRY_MONTH_MM


@dataclass(frozen=True)
class PerennialFit:
    crop: PerennialCropProfile
    variable_scores: dict[str, float]
    categories: CategoryScores
    score: float  # 0..1, the lowest variable score (0 when one is outside the absolute range)
    risks: tuple[Text, ...]
    benefits: tuple[Text, ...]

    @property
    def suitability(self) -> Suitability:
        if self.score == 0:
            return "unsuitable"
        if self.score < MARGINAL_SCORE:
            return "poor"
        return "good" if self.score >= GOOD_SCORE else "fair"


def year_climate(climate: MonthlyClimate) -> YearClimate:
    return YearClimate(
        annual_rainfall_mm=sum(climate.rainfall_mm),
        temperature_c=mean(climate.temperature_c),
        hottest_month_max_c=max(climate.temperature_max_c),
        coldest_month_min_c=min(climate.temperature_min_c),
        dry_months=tuple(i + 1 for i, r in enumerate(climate.rainfall_mm) if r < DRY_MONTH_MM),
    )


def _heat_range(crop: PerennialCropProfile) -> Range:
    limit = crop.temperature_c.abs_max
    return Range(_NO_LOWER_LIMIT_C, _NO_LOWER_LIMIT_C, limit, limit + HEAT_MARGIN_C)


def _span(r: Range, unit: str, decimals: int = 0) -> Text:
    lo, hi = num(r.opt_min, decimals), num(r.opt_max, decimals)
    return Text(f"{lo.en}–{hi.en}{unit}", f"{lo.es}–{hi.es}{unit}")


def _limit_texts(crop: PerennialCropProfile, value: float) -> dict[str, Text]:
    """The sentence for each variable, given its value here."""
    a, the_es = crop.label.en.lower(), crop.the_es
    v0, v1 = num(value), num(value, 1)
    temp, rain = _span(crop.temperature_c, " °C"), _span(crop.rainfall_mm, " mm")
    ph, limit = _span(crop.soil_ph, "", 1), num(crop.temperature_c.abs_max)
    return {
        "temperature": Text(
            f"The mean temperature here is {v1.en} °C; {a} does best at {temp.en}",
            f"La temperatura media aquí es {v1.es} °C; {the_es} rinde mejor con {temp.es}",
        ),
        "rainfall": Text(
            f"About {v0.en} mm of rain a year here; {a} does best with {rain.en}",
            f"Aquí llueven unos {v0.es} mm al año; {the_es} rinde mejor con {rain.es}",
        ),
        "heat": Text(
            f"In the hottest month days average {v1.en} °C, above the {limit.en} °C {a} tolerates",
            f"En el mes más caliente el día promedia {v1.es} °C, más de los {limit.es} °C que "
            f"tolera {the_es}",
        ),
        "frost": Text(
            f"Nights in the coldest month average {v1.en} °C: frost risk",
            f"Las noches del mes más frío promedian {v1.es} °C: riesgo de helada",
        ),
        "soil_ph": Text(
            f"Soil pH here is {v1.en}; {a} does best at pH {ph.en}",
            f"El pH del suelo aquí es {v1.es}; {the_es} rinde mejor con pH {ph.es}",
        ),
    }


def _limit_note(crop: PerennialCropProfile, var: str, value: float, score: float) -> Text | None:
    """One sentence when a variable limits the crop here (score below MARGINAL_SCORE)."""
    if score >= MARGINAL_SCORE:
        return None
    return _limit_texts(crop, value)[var]


def _months(months: tuple[int, ...]) -> Text:
    return Text(
        ", ".join(MONTHS_ABBR_EN[m - 1] for m in months),
        ", ".join(MONTHS_ABBR_ES[m - 1] for m in months),
    )


def dry_season_note(year: YearClimate) -> Text | None:
    """Neutral note on a long dry season: young plants need water then. Same for every crop."""
    n = len(year.dry_months)
    if n < LONG_DRY_SEASON_MONTHS:
        return None
    limit, which = num(DRY_MONTH_MM), _months(year.dry_months)
    return Text(
        f"{n} months with less than {limit.en} mm of rain ({which.en}): young plants will need "
        "watering in those months",
        f"{n} meses con menos de {limit.es} mm de lluvia ({which.es}): las plantas jóvenes van a "
        "necesitar riego en esos meses",
    )


def perennial_fit(
    *,
    crop: PerennialCropProfile,
    year: YearClimate,
    soil: SoilConditions,
    variables: Sequence[str],
) -> PerennialFit:
    raw = {
        "temperature": (year.temperature_c, crop.temperature_c),
        "rainfall": (year.annual_rainfall_mm, crop.rainfall_mm),
        "heat": (year.hottest_month_max_c, _heat_range(crop)),
        "frost": (year.coldest_month_min_c, FROST_RANGE),
        "soil_ph": (soil.ph, crop.soil_ph),
    }
    scores: dict[str, float] = {}
    risks: list[Text] = []
    for var in (v for v in variables if v in PERENNIAL_VARIABLES):
        value, rng = raw[var]
        scores[var] = trapezoid(value, rng)
        note = _limit_note(crop, var, value, scores[var])
        if note is not None:
            risks.append(note)

    def category(name: str) -> float | None:
        values = [s for v, s in scores.items() if CATEGORY_OF[v] == name]
        return mean(values) if values else None

    categories = CategoryScores(
        climate=category("climate"), water=category("water"), soil=category("soil")
    )
    score = min(scores.values(), default=0.0)
    benefits: list[Text] = []
    if scores and all(s == 1.0 for s in scores.values()):
        benefits.append(
            Text(
                f"Temperature, rain and soil pH here are all in the best range for "
                f"{crop.label.en.lower()}",
                f"La temperatura, la lluvia y el pH del suelo aquí están en el mejor rango para "
                f"{crop.the_es}",
            )
        )
    return PerennialFit(
        crop=crop,
        variable_scores=scores,
        categories=categories,
        score=score,
        risks=tuple(risks),
        benefits=tuple(benefits),
    )


_SUITABILITY_TEXT: dict[Suitability, Text] = {
    "good": Text("good fit here", "se adapta bien aquí"),
    "fair": Text("fair fit here, with limits", "se adapta aquí, con limitaciones"),
    "poor": Text("poor fit here", "se adapta poco aquí"),
    "unsuitable": Text("not suited to this place", "no se adapta a este lugar"),
}


def summary(fit: PerennialFit) -> Text:
    """'Cacao: good fit here (score 0.92 of 1).'"""
    s, score = _SUITABILITY_TEXT[fit.suitability], num(fit.score, 2)
    return Text(
        f"{fit.crop.label.en}: {s.en} (score {score.en} of 1)",
        f"{fit.crop.label.es}: {s.es} (puntaje {score.es} de 1)",
    )


def rank(fits: Sequence[PerennialFit]) -> list[PerennialFit]:
    """Best first; ties by crop id so the order is stable."""
    return sorted(fits, key=lambda f: (-f.score, f.crop.id))
