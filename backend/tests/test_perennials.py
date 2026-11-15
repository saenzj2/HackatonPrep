"""Permanent crops scored over the whole year (app/domain/perennials.py), on toy data."""

import pytest

from app.domain.models import MonthlyClimate, PerennialCropProfile, Range, SoilConditions
from app.domain.perennials import (
    DRY_MONTH_MM,
    LONG_DRY_SEASON_MONTHS,
    dry_season_note,
    perennial_fit,
    rank,
    summary,
    year_climate,
)

ALL = ("temperature", "rainfall", "heat", "frost", "soil_ph")


def toy_crop(**overrides) -> PerennialCropProfile:
    values = {
        "id": "cacao",
        "name": "Cacao",
        "name_es": "Cacao",
        "scientific_name": "Theobroma cacao",
        "family": "Malvaceae",
        "temperature_c": Range(10, 20, 30, 40),
        "rainfall_mm": Range(1000, 1500, 3000, 6000),
        "soil_ph": Range(4, 5, 7, 8),
        "max_altitude_m": 900.0,
        "sources": ("toy",),
        **overrides,
    }
    return PerennialCropProfile(**values)


def toy_climate(*, temp=25.0, rain=200.0, tmax=30.0, tmin=20.0, dry_months=()) -> MonthlyClimate:
    """12 equal months; the listed dry months get 10 mm instead."""
    return MonthlyClimate(
        temperature_c=(temp,) * 12,
        rainfall_mm=tuple(10.0 if m in dry_months else rain for m in range(1, 13)),
        temperature_max_c=(tmax,) * 12,
        temperature_min_c=(tmin,) * 12,
    )


SOIL = SoilConditions(ph=6.0, moisture_m3m3=0.3)


def fit(crop=None, climate=None, soil=SOIL, variables=ALL):
    return perennial_fit(
        crop=crop or toy_crop(),
        year=year_climate(climate or toy_climate()),
        soil=soil,
        variables=variables,
    )


def test_year_climate_sums_rain_and_finds_the_extremes():
    climate = MonthlyClimate(
        temperature_c=tuple(float(20 + m) for m in range(12)),
        rainfall_mm=(10.0, 50.0, *([100.0] * 10)),
        temperature_max_c=tuple(float(30 + m) for m in range(12)),
        temperature_min_c=tuple(float(10 + m) for m in range(12)),
    )
    year = year_climate(climate)
    assert year.annual_rainfall_mm == pytest.approx(1060)
    assert year.temperature_c == pytest.approx(25.5)
    assert year.hottest_month_max_c == 41
    assert year.coldest_month_min_c == 10
    assert year.dry_months == (1, 2)  # below DRY_MONTH_MM


def test_rainfall_is_scored_on_the_annual_total():
    # 200 mm x 12 = 2400 mm, inside the optimal 1500-3000: a per-season total would not be.
    assert fit().variable_scores["rainfall"] == 1.0


def test_score_is_the_most_limiting_variable():
    # Annual rain 1250 mm: halfway between abs_min 1000 and opt_min 1500 → 0.5; the rest are 1.
    result = fit(climate=toy_climate(rain=1250 / 12))
    assert result.variable_scores["rainfall"] == pytest.approx(0.5)
    assert result.score == pytest.approx(0.5)


def test_one_variable_outside_the_absolute_range_makes_it_unsuitable():
    result = fit(soil=SoilConditions(ph=3.5, moisture_m3m3=0.3))
    assert result.score == 0
    assert result.suitability == "unsuitable"


@pytest.mark.parametrize(
    ("rain_mm_year", "suitability"),
    [(2400, "good"), (1450, "good"), (1300, "fair"), (1100, "poor"), (900, "unsuitable")],
)
def test_suitability_words(rain_mm_year, suitability):
    assert fit(climate=toy_climate(rain=rain_mm_year / 12)).suitability == suitability


def test_heat_uses_the_hottest_month_against_the_absolute_max():
    # abs_max 40, margin 6: a hottest month of 43 °C sits halfway → 0.5
    assert fit(climate=toy_climate(tmax=43.0)).variable_scores["heat"] == pytest.approx(0.5)


def test_soil_moisture_is_never_scored():
    result = fit(variables=(*ALL, "soil_moisture"))
    assert "soil_moisture" not in result.variable_scores


def test_limiting_variable_gets_a_bilingual_note_with_the_value():
    result = fit(climate=toy_climate(rain=1100 / 12))
    assert len(result.risks) == 1
    assert result.risks[0].en == (
        "About 1100 mm of rain a year here; cacao does best with 1500–3000 mm"
    )
    assert result.risks[0].es == (
        "Aquí llueven unos 1100 mm al año; el cacao rinde mejor con 1500–3000 mm"
    )


def test_all_optimal_gives_a_benefit_and_no_risk():
    result = fit()
    assert result.risks == ()
    assert len(result.benefits) == 1


def test_dry_season_note_from_the_threshold_up():
    short = year_climate(toy_climate(dry_months=tuple(range(1, LONG_DRY_SEASON_MONTHS))))
    long = year_climate(toy_climate(dry_months=tuple(range(1, LONG_DRY_SEASON_MONTHS + 1))))
    assert dry_season_note(short) is None
    note = dry_season_note(long)
    assert note is not None
    assert note.es == (
        f"4 meses con menos de {DRY_MONTH_MM:.0f} mm de lluvia (ene, feb, mar, abr): las plantas "
        "jóvenes van a necesitar riego en esos meses"
    )


def test_rank_puts_the_best_first_and_breaks_ties_by_id():
    good = fit(crop=toy_crop(id="b"))
    tie = fit(crop=toy_crop(id="a"))
    bad = fit(crop=toy_crop(id="c", soil_ph=Range(6.5, 7.5, 8, 9)))
    assert [f.crop.id for f in rank([bad, good, tie])] == ["a", "b", "c"]


def test_summary_uses_the_spanish_article_and_decimal_comma():
    result = fit(crop=toy_crop(name="Pineapple", name_es="Piña", gender_es="f"))
    assert summary(result).es == "Piña: se adapta bien aquí (puntaje 1,00 de 1)"
