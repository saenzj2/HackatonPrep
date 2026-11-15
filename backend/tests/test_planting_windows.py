"""Planting windows: best sowing months per crop. Toy climate and crops only."""

import pytest

from app.domain.models import CategoryScores, CropSeasonFit, MonthlyClimate, Season, Weights
from app.domain.planting_windows import (
    SowingMonth,
    cycle_months,
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
    """Apr (dry Apr + 2 rainy months) to Oct (2 rainy months + dry Dec) still reach 400 mm."""
    assert windows_for(RAINY_MAY_TO_NOV) == [(4, 10)]


def test_window_can_wrap_the_year():
    rainy_nov_to_may = RAINY_MAY_TO_NOV[6:] + RAINY_MAY_TO_NOV[:6]
    assert windows_for(rainy_nov_to_may) == [(10, 4)]


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
