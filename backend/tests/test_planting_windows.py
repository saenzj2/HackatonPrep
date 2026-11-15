"""Planting windows: best sowing months per crop. Toy climate and crops only."""

from dataclasses import replace

import pytest

from app.domain.models import (
    CategoryScores,
    CropSeasonFit,
    MonthlyClimate,
    Season,
    SoilConditions,
    Weights,
)
from app.domain.planting_windows import (
    SowingMonth,
    cycle_months,
    dry_month_check,
    fixed_limits,
    planting_windows,
    sowing_calendar,
)
from app.domain.suitability import crop_season_fit, season_climate
from tests.test_domain import ALL_VARS, GOOD_SOIL, crop

EQUAL = Weights(1, 1, 1)
RAINY_MAY_TO_NOV = tuple(200.0 if 5 <= m <= 11 else 10.0 for m in range(1, 13))


def climate(rain: tuple[float, ...]) -> MonthlyClimate:
    return MonthlyClimate(
        temperature_c=(25.0,) * 12,
        rainfall_mm=rain,
        temperature_max_c=(30.0,) * 12,
        temperature_min_c=(20.0,) * 12,
    )


def windows_for(rain):
    """Toy crop: 90-day cycle (3 months), optimal rain 400..1200 mm over the cycle."""
    cal = sowing_calendar(
        crop("beans"), climate=climate(rain), soil=GOOD_SOIL, weights=EQUAL, variables=ALL_VARS
    )
    return [(w.first_month, w.last_month) for w in planting_windows(cal)]


@pytest.mark.parametrize(
    ("sowing", "days", "expected"),
    [(5, 90, (5, 6, 7)), (5, 120, (5, 6, 7, 8)), (11, 90, (11, 12, 1)), (3, 10, (3,))],
)
def test_cycle_months_rounds_up_and_wraps_the_year(sowing, days, expected):
    assert cycle_months(sowing, days) == expected


def test_each_sowing_month_uses_the_rotation_scoring():
    cal = sowing_calendar(
        crop("beans"),
        climate=climate(RAINY_MAY_TO_NOV),
        soil=GOOD_SOIL,
        weights=EQUAL,
        variables=ALL_VARS,
    )
    may = Season("x", (5, 6, 7))
    expected = crop_season_fit(
        crop("beans"),
        season_climate(climate(RAINY_MAY_TO_NOV), may),
        GOOD_SOIL,
        EQUAL.normalized(),
        ALL_VARS,
    )
    assert len(cal) == 12
    assert cal[4].fit.season.months == (5, 6, 7)
    assert cal[4].score == pytest.approx(expected.score)


def test_window_covers_sowing_months_whose_cycle_gets_enough_rain():
    """Oct (Oct, Nov rainy; dry Dec is the harvest month) is good. Apr reaches 400 mm over the cycle
    but Apr itself gets 10 mm: the dry-month check rejects it."""
    assert windows_for(RAINY_MAY_TO_NOV) == [(5, 10)]


def test_window_can_wrap_the_year():
    rainy_nov_to_may = RAINY_MAY_TO_NOV[6:] + RAINY_MAY_TO_NOV[:6]
    assert windows_for(rainy_nov_to_may) == [(11, 4)]


def test_no_window_when_no_month_is_good():
    assert windows_for((10.0,) * 12) == []


def month(m: int, score: float, weakest: float = 1.0) -> SowingMonth:
    """A made-up sowing month: overall score plus its weakest variable score."""
    fit = CropSeasonFit(
        crop=crop("x"),
        season=Season("x", (m,)),
        variable_scores={"rainfall": weakest, "temperature": 1.0},
        categories=CategoryScores(climate=1.0, water=weakest, soil=1.0),
        score=score,
    )
    return SowingMonth(sowing_month=m, fit=fit)


def year(good_months: set[int]) -> list[SowingMonth]:
    return [month(m, 1.0 if m in good_months else 0.0) for m in range(1, 13)]


@pytest.mark.parametrize(
    ("good", "expected"),
    [
        (set(range(1, 13)), [(1, 12)]),  # all year
        ({3, 4, 5, 9, 10}, [(3, 5), (9, 10)]),  # two separate windows
        (set(range(1, 13)) - {6, 7}, [(8, 5)]),  # most of the year, wrapping Dec → Jan
    ],
)
def test_window_shapes(good, expected):
    assert [(w.first_month, w.last_month) for w in planting_windows(year(good))] == expected


def test_high_score_with_one_marginal_variable_is_not_good():
    """Overall 0.85 but rainfall at 0.1: the average hides a factor near its limit."""
    months = [month(m, 0.85, weakest=0.1) for m in range(1, 13)]
    assert not months[0].is_good()
    assert planting_windows(months) == ()


def _calendar_with_ph(ph: float):
    """Toy crop (pH ideal 5.5-7.0, limits 4.5-8.5) in the rainy May-Nov toy climate."""
    soil = SoilConditions(ph=ph, moisture_m3m3=0.3)
    return sowing_calendar(
        crop("beans"),
        climate=climate(RAINY_MAY_TO_NOV),
        soil=soil,
        weights=EQUAL,
        variables=ALL_VARS,
    )


def test_low_ph_lowers_scores_but_does_not_veto_every_month():
    """pH 4.7 scores 0.2, the same in all 12 months: it's reported once, windows stay."""
    cal = _calendar_with_ph(4.7)
    assert fixed_limits(cal) == {"soil_ph": pytest.approx(0.2)}
    assert [(w.first_month, w.last_month) for w in planting_windows(cal)] == [(5, 10)]


def test_ph_outside_the_absolute_range_leaves_no_window():
    cal = _calendar_with_ph(4.0)
    assert fixed_limits(cal) == {"soil_ph": 0.0}
    assert planting_windows(cal) == ()


def test_waterlogging_flags_months_but_never_removes_them_from_a_window():
    """Saturated all year (wetness 1.0) for a crop that needs drainage: same window, every month
    flagged, scores lowered (rotations still feel it)."""
    dry = SoilConditions(ph=6.0, moisture_m3m3=0.3)
    wet = SoilConditions(ph=6.0, moisture_m3m3=0.3, wetness_monthly=(1.0,) * 12)
    needs_drainage = replace(crop("beans"), needs_good_drainage=True)
    cals = {
        name: sowing_calendar(
            needs_drainage,
            climate=climate(RAINY_MAY_TO_NOV),
            soil=soil,
            weights=EQUAL,
            variables=ALL_VARS,
        )
        for name, soil in (("dry", dry), ("wet", wet))
    }
    windows = {
        name: [(w.first_month, w.last_month) for w in planting_windows(c)]
        for name, c in cals.items()
    }
    assert windows["wet"] == windows["dry"] == [(5, 10)]
    assert all(m.fit.waterlogging_warning for m in cals["wet"])
    assert cals["wet"][5].score < cals["dry"][5].score


# ---------------------------------------------------------------- dry-month check
# Toy crop: rain 200/400 mm per cycle, 90 days → 3 months in field → limit 200/4 = 50 mm,
# optimum 400/4 = 100 mm, passes at 75 mm (MARGINAL_SCORE 0.5).


@pytest.mark.parametrize(
    ("driest_mm", "score", "passes"),
    [
        (50.0, 0.0, False),
        (74.0, 0.48, False),
        (75.0, 0.5, True),
        (100.0, 1.0, True),
        (300.0, 1.0, True),
    ],
)
def test_dry_month_ramp_edges(driest_mm, score, passes):
    rain = tuple(driest_mm if m == 5 else 1000.0 for m in range(1, 13))  # May is the driest
    dry = dry_month_check(crop("beans"), climate(rain), (5, 6, 7))
    assert dry.month == 5
    assert dry.score == pytest.approx(score)
    assert (dry.score >= 0.5) is passes


def test_dry_month_check_never_looks_at_the_harvest_month():
    rain = tuple(10.0 if m == 7 else 200.0 for m in range(1, 13))  # only July (harvest) is dry
    dry = dry_month_check(crop("beans"), climate(rain), (5, 6, 7))
    assert dry.month != 7
    assert dry.score == 1.0


def test_one_month_cycle_has_nothing_to_check():
    assert dry_month_check(crop("beans"), climate(RAINY_MAY_TO_NOV), (5,)) is None
