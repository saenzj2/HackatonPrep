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
from app.domain.ranking import (
    MONOCULTURE_PENALTY,
    SAME_FAMILY_PENALTY,
    explain,
    rank_rotations,
)
from app.domain.suitability import (
    HEAT_MARGIN_C,
    crop_season_fit,
    season_climate,
    trapezoid,
)
from app.errors import DomainInvariantError

R = Range(abs_min=10, opt_min=20, opt_max=30, abs_max=40)
ALL_VARS = ["temperature", "rainfall", "soil_ph", "soil_moisture", "heat", "frost"]


DEFAULT_TEMP = Range(10, 18, 32, 40)


def crop(
    id_: str, legume: bool = False, temp: Range = DEFAULT_TEMP, family: str | None = None
) -> CropProfile:
    return CropProfile(
        id=id_,
        name=id_.title(),
        scientific_name="x",
        family=family or ("Fabaceae" if legume else "Poaceae"),
        is_legume=legume,
        cycle_days=90,
        temperature_c=temp,
        rainfall_mm=Range(200, 400, 1200, 2000),
        soil_ph=Range(4.5, 5.5, 7.0, 8.5),
    )


GOOD_CLIMATE = MonthlyClimate(
    temperature_c=(25.0,) * 12,
    rainfall_mm=(200.0,) * 12,
    temperature_max_c=(30.0,) * 12,
    temperature_min_c=(20.0,) * 12,
)
GOOD_SOIL = SoilConditions(ph=6.0, moisture_m3m3=0.3)
SEASONS = [Season("a", (5, 6, 7)), Season("b", (9, 10, 11))]
EQUAL = Weights(1, 1, 1)


def rank(crops: list[CropProfile], seasons: list[Season] = SEASONS, top_n: int | None = 5):
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
    climate = MonthlyClimate(
        temperature_c=tuple(range(12)),
        rainfall_mm=tuple(range(12)),
        temperature_max_c=tuple(range(10, 22)),
        temperature_min_c=tuple(range(12)),
    )
    sc = season_climate(climate, Season("x", (1, 2, 3)))
    assert sc.temperature_c == 1.0
    assert sc.rainfall_mm_per_month == 1.0
    assert sc.temperature_max_c == 11.0


def test_season_climate_uses_coldest_month_for_frost():
    climate = MonthlyClimate(
        temperature_c=(10.0,) * 12,
        rainfall_mm=(100.0,) * 12,
        temperature_max_c=(15.0,) * 12,
        temperature_min_c=(8.0, 2.0, 6.0) + (8.0,) * 9,
    )
    assert season_climate(climate, Season("x", (1, 2, 3))).temperature_min_c == 2.0


def test_monthly_climate_needs_twelve_daily_extremes():
    with pytest.raises(DomainInvariantError, match="12 values"):
        MonthlyClimate(
            temperature_c=(25.0,) * 12,
            rainfall_mm=(200.0,) * 12,
            temperature_max_c=(30.0,) * 11,
            temperature_min_c=(20.0,) * 12,
        )


def sc_with(
    temperature_c: float = 25.0,
    rainfall_mm_per_month: float = 200.0,
    temperature_max_c: float = 30.0,
    temperature_min_c: float = 20.0,
) -> SeasonClimate:
    return SeasonClimate(
        SEASONS[0],
        temperature_c=temperature_c,
        rainfall_mm_per_month=rainfall_mm_per_month,
        temperature_max_c=temperature_max_c,
        temperature_min_c=temperature_min_c,
    )


@pytest.mark.parametrize(
    ("tmax", "expected"),
    [(30.0, 1.0), (40.0, 1.0), (40.0 + HEAT_MARGIN_C / 2, 0.5), (40.0 + HEAT_MARGIN_C, 0.0)],
)
def test_heat_score_drops_above_crop_absolute_max(tmax, expected):
    """DEFAULT_TEMP abs_max is 40 °C."""
    fit = crop_season_fit(
        crop("maize"), sc_with(temperature_max_c=tmax), GOOD_SOIL, EQUAL, ["heat"]
    )
    assert fit.variable_scores["heat"] == pytest.approx(expected)


def test_heat_stress_is_reported_as_risk():
    fit = crop_season_fit(
        crop("maize"), sc_with(temperature_max_c=42.0), GOOD_SOIL, EQUAL, ["heat"]
    )
    assert any("heat stress" in r for r in fit.risks)


@pytest.mark.parametrize(("tmin", "expected"), [(-2.0, 0.0), (0.0, 0.0), (2.5, 0.5), (5.0, 1.0)])
def test_frost_score(tmin, expected):
    fit = crop_season_fit(
        crop("maize"), sc_with(temperature_min_c=tmin), GOOD_SOIL, EQUAL, ["frost"]
    )
    assert fit.variable_scores["frost"] == pytest.approx(expected)


def test_frost_risk_is_reported():
    fit = crop_season_fit(
        crop("maize"), sc_with(temperature_min_c=2.0), GOOD_SOIL, EQUAL, ["frost"]
    )
    assert any("frost risk" in r for r in fit.risks)


def test_no_risks_in_good_conditions():
    fit = crop_season_fit(crop("maize"), sc_with(), GOOD_SOIL, EQUAL.normalized(), ALL_VARS)
    assert fit.risks == ()


def test_marginal_variable_is_reported_as_risk():
    """70 mm/month × 90 days ≈ 207 mm/cycle; abs_min 200, opt_min 400: barely viable."""
    fit = crop_season_fit(
        crop("maize"), sc_with(rainfall_mm_per_month=70.0), GOOD_SOIL, EQUAL, ["rainfall"]
    )
    assert 0 < fit.variable_scores["rainfall"] < 0.5
    assert any("rainfall" in r for r in fit.risks)


def test_fit_is_zero_when_any_variable_outside_absolute_limits():
    sc = sc_with(temperature_c=45.0)
    fit = crop_season_fit(crop("maize"), sc, GOOD_SOIL, EQUAL.normalized(), ALL_VARS)
    assert fit.score == 0.0
    assert any("temperature" in n and "above" in n for n in fit.risks)


def test_tiny_scores_are_not_rounded_to_zero():
    """Just inside the absolute limit is bad but viable; only output gets rounded (services)."""
    sc = sc_with(temperature_c=39.9999)
    fit = crop_season_fit(crop("maize"), sc, GOOD_SOIL, EQUAL.normalized(), ALL_VARS)
    assert 0 < fit.variable_scores["temperature"] < 0.001
    assert fit.score > 0


def test_fit_only_uses_enabled_variables():
    sc = sc_with(temperature_c=45.0)
    fit = crop_season_fit(crop("maize"), sc, GOOD_SOIL, EQUAL.normalized(), ["soil_ph"])
    assert set(fit.variable_scores) == {"soil_ph"}
    assert fit.categories.climate is None
    assert fit.score == 1.0


def test_priorities_change_the_score():
    sc = sc_with(rainfall_mm_per_month=100.0)  # dry-ish: ~296 mm/cycle, below optimum
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
    assert any("monoculture" in n for n in mono.risks)


def scores_by_ids(crops):
    return {tuple(f.crop.id for f in r.sequence): r.score for r in rank(crops, top_n=None)}


def test_same_family_penalty_is_between_rotation_and_monoculture():
    """maize and rice are both Poaceae; every crop fits perfectly, so only adjustments differ."""
    scores = scores_by_ids([crop("maize"), crop("rice"), crop("soy", family="Brassicaceae")])
    assert scores[("maize", "soy")] == pytest.approx(1.0)
    assert scores[("maize", "rice")] == pytest.approx(1.0 - SAME_FAMILY_PENALTY)
    assert scores[("maize", "maize")] == pytest.approx(1.0 - MONOCULTURE_PENALTY)


def test_same_family_is_a_risk_and_family_change_a_benefit():
    results = {
        tuple(f.crop.id for f in r.sequence): r
        for r in rank([crop("maize"), crop("rice"), crop("beans", legume=True)], top_n=None)
    }
    assert any("same family (Poaceae)" in x for x in results[("maize", "rice")].risks)
    assert any("family change" in x for x in results[("maize", "beans")].benefits)
    assert any("fixes nitrogen" in x for x in results[("maize", "beans")].benefits)


def test_strong_categories_are_benefits():
    (best,) = rank([crop("maize"), crop("beans", legume=True)], top_n=1)
    assert any("Strong water fit" in b for b in best.benefits)


def test_rank_without_top_n_returns_every_combination():
    assert len(rank([crop("a"), crop("b"), crop("c")], top_n=None)) == 9


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
