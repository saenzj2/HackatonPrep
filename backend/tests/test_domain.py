import pytest

from app.domain.models import (
    CropProfile,
    MonthlyClimate,
    Range,
    Season,
    SeasonClimate,
    SoilConditions,
    Weights,
)
from app.domain.ranking import explain, rank_rotations
from app.domain.suitability import crop_season_fit, season_climate, trapezoid
from app.errors import DomainInvariantError

R = Range(abs_min=10, opt_min=20, opt_max=30, abs_max=40)
ALL_VARS = ["temperature", "rainfall", "soil_ph", "soil_moisture"]


DEFAULT_TEMP = Range(10, 18, 32, 40)


def crop(id_: str, legume: bool = False, temp: Range = DEFAULT_TEMP) -> CropProfile:
    return CropProfile(
        id=id_,
        name=id_.title(),
        scientific_name="x",
        family="Fabaceae" if legume else "Poaceae",
        is_legume=legume,
        cycle_days=90,
        temperature_c=temp,
        rainfall_mm=Range(200, 400, 1200, 2000),
        soil_ph=Range(4.5, 5.5, 7.0, 8.5),
    )


GOOD_CLIMATE = MonthlyClimate(temperature_c=(25.0,) * 12, rainfall_mm=(200.0,) * 12)
GOOD_SOIL = SoilConditions(ph=6.0, moisture_m3m3=0.3)
SEASONS = [Season("a", (5, 6, 7)), Season("b", (9, 10, 11))]
EQUAL = Weights(1, 1, 1)


def rank(crops: list[CropProfile], seasons: list[Season] = SEASONS, top_n: int = 5):
    return rank_rotations(
        crops=crops,
        seasons=seasons,
        climate=GOOD_CLIMATE,
        soil=GOOD_SOIL,
        weights=EQUAL,
        variables=ALL_VARS,
        top_n=top_n,
    )


@pytest.mark.parametrize(
    ("x", "expected"),
    [(5, 0.0), (10, 0.0), (15, 0.5), (20, 1.0), (25, 1.0), (30, 1.0), (35, 0.5), (40, 0.0)],
)
def test_trapezoid(x, expected):
    assert trapezoid(x, R) == pytest.approx(expected)


def test_trapezoid_with_no_ramp():
    assert trapezoid(10.5, Range(10, 10, 30, 30)) == 1.0


def test_range_rejects_bad_order():
    with pytest.raises(DomainInvariantError, match="abs_min <= opt_min"):
        Range(abs_min=20, opt_min=10, opt_max=30, abs_max=40)


def test_weights_normalized():
    w = Weights(2, 1, 1).normalized()
    assert (w.water, w.soil, w.climate) == pytest.approx((0.5, 0.25, 0.25))
    with pytest.raises(DomainInvariantError, match="At least one priority weight"):
        Weights(0, 0, 0).normalized()


def test_season_climate_averages_months():
    climate = MonthlyClimate(temperature_c=tuple(range(12)), rainfall_mm=tuple(range(12)))
    sc = season_climate(climate, Season("x", (1, 2, 3)))
    assert sc.temperature_c == 1.0
    assert sc.rainfall_mm_per_month == 1.0


def test_fit_is_zero_when_any_variable_outside_absolute_limits():
    sc = SeasonClimate(SEASONS[0], temperature_c=45.0, rainfall_mm_per_month=200.0)
    fit = crop_season_fit(crop("maize"), sc, GOOD_SOIL, EQUAL.normalized(), ALL_VARS)
    assert fit.score == 0.0
    assert any("temperature" in n and "above" in n for n in fit.notes)


def test_tiny_scores_are_not_rounded_to_zero():
    """Just inside the absolute limit is bad but viable; only output gets rounded (services)."""
    sc = SeasonClimate(SEASONS[0], temperature_c=39.9999, rainfall_mm_per_month=200.0)
    fit = crop_season_fit(crop("maize"), sc, GOOD_SOIL, EQUAL.normalized(), ALL_VARS)
    assert 0 < fit.variable_scores["temperature"] < 0.001
    assert fit.score > 0


def test_fit_only_uses_enabled_variables():
    sc = SeasonClimate(SEASONS[0], temperature_c=45.0, rainfall_mm_per_month=200.0)
    fit = crop_season_fit(crop("maize"), sc, GOOD_SOIL, EQUAL.normalized(), ["soil_ph"])
    assert set(fit.variable_scores) == {"soil_ph"}
    assert fit.categories.climate is None
    assert fit.score == 1.0


def test_priorities_change_the_score():
    sc = SeasonClimate(
        SEASONS[0], temperature_c=25.0, rainfall_mm_per_month=100.0
    )  # dry-ish: ~296 mm/cycle, below optimum
    c = crop("maize")
    water_first = crop_season_fit(c, sc, GOOD_SOIL, Weights(1, 0, 0), ALL_VARS)
    climate_first = crop_season_fit(c, sc, GOOD_SOIL, Weights(0, 0, 1), ALL_VARS)
    assert water_first.score < climate_first.score


def test_legume_after_cereal_beats_monoculture():
    crops = [crop("maize"), crop("beans", legume=True)]
    results = rank(crops, top_n=10)
    ids = [tuple(f.crop.id for f in r.sequence) for r in results]
    assert len(results) == 4  # 2 crops ^ 2 seasons
    assert set(ids[:2]) == {("maize", "beans"), ("beans", "maize")}
    assert results[-1].score < results[0].score
    mono = next(r for r in results if ids[results.index(r)] == ("maize", "maize"))
    assert any("monoculture" in n for n in mono.notes)


def test_non_viable_rotations_rank_last():
    too_cold_for = Range(26, 28, 32, 40)  # fails at 25 °C
    crops = [crop("maize"), crop("tropical", temp=too_cold_for)]
    results = rank(crops, top_n=10)
    assert results[0].viable
    assert not results[-1].viable
    assert "not recommended" in explain(results[-1])


def test_rank_requires_two_seasons():
    with pytest.raises(DomainInvariantError, match="two seasons"):
        rank([crop("a")], seasons=SEASONS[:1])


def test_ranking_is_deterministic():
    crops = [crop("maize"), crop("beans", legume=True), crop("rice")]
    a = rank(crops)
    b = rank(crops)
    assert a == b
