import math
from dataclasses import replace

import pytest

from app.domain.erosion import (
    ErosionRisk,
    RainfallSummary,
    RainfallThresholds,
    assess_erosion,
    combined_risk,
    rainfall_risk,
    slope_pct,
    summarize_rainfall,
    terrain_risk,
)
from app.domain.models import (
    CropProfile,
    MonthlyClimate,
    Range,
    Season,
    SeasonClimate,
    SoilConditions,
    TerrainSample,
    Weights,
    level_for,
)
from app.domain.ranking import (
    LOCAL_REVIEW_UNSCORED,
    NO_BENEFIT,
    STRONG_CATEGORY,
    explain,
    rank_rotations,
)
from app.domain.rotation_rules import MONOCULTURE_PENALTY, SAME_FAMILY_PENALTY
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
        root_depth_m=1.0,
        is_cover_crop=False,
        forage_value=0.67,
        nutrition_density=0.67,
        mycorrhizal_affinity=0.67,
        nitrogen_demand=0.67,
        market_note="",
        sources=("test",),
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


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.0, "none"),
        (0.01, "low"),
        (0.33, "low"),
        (0.5, "medium"),
        (0.67, "medium"),
        (0.8, "high"),
        (1.0, "high"),
    ],
)
def test_level_for_maps_score_to_word(score, expected):
    assert level_for(score) == expected


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_level_for_rejects_score_outside_0_1(score):
    with pytest.raises(DomainInvariantError, match="Trait score must be in"):
        level_for(score)


@pytest.mark.parametrize("depth", [0.0, -1.0, 6.0])
def test_crop_rejects_implausible_root_depth(depth):
    with pytest.raises(DomainInvariantError, match="root_depth_m"):
        replace(crop("x"), root_depth_m=depth)


@pytest.mark.parametrize("score", [-0.1, 1.5])
def test_crop_rejects_trait_score_outside_0_1(score):
    with pytest.raises(DomainInvariantError, match="trait scores"):
        replace(crop("x"), forage_value=score)


def test_crop_requires_a_source():
    with pytest.raises(DomainInvariantError, match="at least one source"):
        replace(crop("x"), sources=())


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
    assert any("nitrogen from the air" in x for x in results[("maize", "beans")].benefits)


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


# ---------------------------------------------------------------- erosion
LOW, MEDIUM, HIGH = ErosionRisk.LOW, ErosionRisk.MEDIUM, ErosionRisk.HIGH


def terrain(*, north=100.0, south=100.0, east=100.0, west=100.0, spacing=50.0):
    return TerrainSample(
        elevation_m=100.0,
        north_m=north,
        south_m=south,
        east_m=east,
        west_m=west,
        spacing_ns_m=spacing,
        spacing_ew_m=spacing,
    )


def rain_summary(*, avg=1.0, heavy_days=0, max_mm=10.0, days=30):
    return RainfallSummary(
        total_mm=avg * days,
        avg_daily_mm=avg,
        heavy_rain_days=heavy_days,
        max_daily_mm=max_mm,
        valid_days=days,
    )


def test_slope_is_zero_on_flat_ground():
    assert slope_pct(terrain()) == 0


def test_slope_uses_neighbours_two_spacings_apart():
    # 10 m rise over 2 × 50 m along x → 10 %
    assert slope_pct(terrain(east=105.0, west=95.0)) == pytest.approx(10.0)


def test_slope_combines_both_axes():
    # 3 % along x and 4 % along y → 5 % (3-4-5 triangle)
    assert slope_pct(terrain(east=101.5, west=98.5, north=102.0, south=98.0)) == pytest.approx(5.0)


def test_terrain_sample_rejects_zero_spacing():
    with pytest.raises(DomainInvariantError, match="spacings"):
        terrain(spacing=0.0)


@pytest.mark.parametrize(
    ("slope", "expected"),
    [(0.0, LOW), (4.99, LOW), (5.0, MEDIUM), (15.0, MEDIUM), (15.01, HIGH), (60.0, HIGH)],
)
def test_terrain_risk_classes(slope, expected):
    assert terrain_risk(slope) == expected


def test_summarize_rainfall_skips_missing_days():
    s = summarize_rainfall([10.0, math.nan, 40.0, 0.0])
    assert s.valid_days == 3
    assert s.total_mm == 50.0
    assert s.avg_daily_mm == pytest.approx(50 / 3)
    assert s.heavy_rain_days == 1  # 40 mm ≥ 30 mm
    assert s.max_daily_mm == 40.0


def test_summarize_rainfall_counts_exactly_30_mm_as_heavy():
    assert summarize_rainfall([30.0, 29.9]).heavy_rain_days == 1


def test_summarize_rainfall_rejects_no_data():
    with pytest.raises(DomainInvariantError, match="at least one day"):
        summarize_rainfall([math.nan, math.nan])


@pytest.mark.parametrize(
    ("summary", "expected"),
    [
        (rain_summary(), LOW),
        (rain_summary(avg=4.0), MEDIUM),  # average intensity alone
        (rain_summary(avg=8.0), HIGH),
        (rain_summary(heavy_days=1), MEDIUM),  # 1 heavy day per 30 days
        (rain_summary(heavy_days=3), HIGH),
        (rain_summary(avg=8.0, heavy_days=1), HIGH),  # the worse of the two wins
    ],
)
def test_rainfall_risk_is_worst_indicator(summary, expected):
    assert rainfall_risk(summary) == expected


def test_rainfall_risk_ignores_the_wettest_day():
    # Reported, not scored: it grows with the period length (reviewer #3)
    assert rainfall_risk(rain_summary(max_mm=150.0)) == LOW


def test_rainfall_risk_scales_heavy_days_with_period_length():
    # The same 3 heavy days: 3 per 30 days (HIGH), 1 per 30 (MEDIUM), ~0.25 per 30 (LOW)
    assert rainfall_risk(rain_summary(heavy_days=3, days=30)) == HIGH
    assert rainfall_risk(rain_summary(heavy_days=3, days=90)) == MEDIUM
    assert rainfall_risk(rain_summary(heavy_days=3, days=365)) == LOW


def test_rainfall_thresholds_are_configurable():
    strict = RainfallThresholds(avg_daily_medium_mm=0.5, avg_daily_high_mm=0.9)
    assert rainfall_risk(rain_summary(avg=1.0), strict) == HIGH


def test_rainfall_thresholds_reject_medium_above_high():
    with pytest.raises(DomainInvariantError, match="medium <= high"):
        RainfallThresholds(avg_daily_medium_mm=9.0, avg_daily_high_mm=8.0)


@pytest.mark.parametrize(
    ("terrain_level", "rain_level", "expected"),
    [
        (LOW, LOW, LOW),
        (LOW, MEDIUM, LOW),
        (LOW, HIGH, MEDIUM),
        (MEDIUM, LOW, MEDIUM),
        (MEDIUM, MEDIUM, MEDIUM),
        (MEDIUM, HIGH, HIGH),
        (HIGH, LOW, HIGH),
        (HIGH, HIGH, HIGH),
    ],
)
def test_combined_risk_matrix(terrain_level, rain_level, expected):
    assert combined_risk(terrain_level, rain_level) == expected


@pytest.mark.parametrize("terrain_level", list(ErosionRisk))
@pytest.mark.parametrize("rain_level", list(ErosionRisk))
def test_combined_risk_never_below_terrain(terrain_level, rain_level):
    assert combined_risk(terrain_level, rain_level) >= terrain_level


def test_assess_erosion_end_to_end():
    # 10 % slope (medium) + 2 heavy days in 10 days (6 per 30 → high rain) → high
    a = assess_erosion(
        terrain=terrain(east=105.0, west=95.0), daily_rainfall_mm=[40.0, 35.0] + [0.0] * 8
    )
    assert a.slope_pct == pytest.approx(10.0)
    assert a.terrain_erosion_risk == MEDIUM
    assert a.rainfall_erosion_risk == HIGH
    assert a.combined_erosion_risk == HIGH


def test_every_rotation_ends_with_local_review_items():
    for r in rank([crop("maize"), crop("beans", legume=True)], top_n=None):
        assert r.risks[-1] == LOCAL_REVIEW_UNSCORED
        assert r.risks[-2].startswith("Local review: check sowing dates")


def test_local_review_names_each_crop_and_season():
    (r,) = rank([crop("maize"), crop("beans", legume=True)], top_n=1)
    names = [f"{f.crop.name} in {f.season.name}" for f in r.sequence]
    assert ", ".join(names) in r.risks[-2]


def test_rotation_with_good_fit_and_family_change_still_has_local_review_risks():
    """maize -> beans has no rule risk; without local review its risks would be empty."""
    (r,) = rank([crop("maize"), crop("beans", legume=True)], top_n=1)
    assert [x for x in r.risks if not x.startswith("Local review")] == []
    assert len(r.risks) == 2


def test_rotation_without_any_benefit_says_so():
    """Monoculture of a crop that fits poorly: no rule benefit and no strong category."""
    poor = replace(
        crop("maize", temp=Range(20, 35, 38, 45)),  # 25 °C: low on the cold ramp
        rainfall_mm=Range(100, 1000, 1500, 2000),  # ~600 mm per cycle: on the dry ramp
        soil_ph=Range(5, 6.5, 7, 8),  # pH 6: on the acid ramp
    )
    (r,) = rank([poor], top_n=None)
    assert all(v < STRONG_CATEGORY for v in vars(r.breakdown).values() if v is not None)
    assert r.benefits == (NO_BENEFIT,)


def test_rotation_with_a_benefit_does_not_say_none_found():
    (r,) = rank([crop("maize"), crop("beans", legume=True)], top_n=1)
    assert NO_BENEFIT not in r.benefits
