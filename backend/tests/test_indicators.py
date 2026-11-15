"""Monthly field indicators: domain rules (toy data) and the service on the real POWER fixture."""

import math
from datetime import date, timedelta

import pandas as pd
import pytest

from app.domain.indicators import (
    DRY_DAY_MM,
    EXTREME_RAIN_MM,
    FROST_MIN_C,
    HEAT_STRESS_MAX_C,
    monthly_indicators,
)
from app.errors import DomainInvariantError
from app.integrations.mock import MockClimate
from app.integrations.nasa_power import parse_daily
from app.services import field_indicators
from tests.conftest import load_fixture

NAN = math.nan


def days_from(start: date, n: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


def one_month(rain, temps=None, **extrema):
    """Indicators for a short toy series that starts on Jan 1 (so it stays in one month)."""
    temps = temps if temps is not None else [20.0] * len(rain)
    (result,) = monthly_indicators(
        dates=days_from(date(2026, 1, 1), len(rain)),
        temperature_c=temps,
        rainfall_mm=rain,
        **extrema,
    )
    return result


# ---------------------------------------------------------------- domain


def test_thresholds_match_the_documented_values():
    assert (DRY_DAY_MM, EXTREME_RAIN_MM, HEAT_STRESS_MAX_C, FROST_MIN_C) == (1.0, 30.0, 35.0, 0.0)


def test_monthly_indicators_mean_temperature_and_total_rain():
    m = one_month([0.0, 10.0, 20.0], temps=[18.0, 20.0, 22.0])
    assert m.mean_temperature_c == pytest.approx(20.0)
    assert m.total_rainfall_mm == pytest.approx(30.0)


def test_monthly_indicators_dry_day_is_strictly_below_1_mm():
    assert one_month([0.99, 1.0, 0.0]).dry_days == 2


def test_monthly_indicators_extreme_rain_counts_exactly_30_mm():
    assert one_month([30.0, 29.9, 45.0]).extreme_rain_days == 2


def test_monthly_indicators_longest_dry_spell():
    assert one_month([0.0, 0.0, 5.0, 0.0, 0.0, 0.0, 2.0]).longest_dry_spell_days == 3


def test_monthly_indicators_missing_day_breaks_a_dry_spell():
    assert one_month([0.0, 0.0, NAN, 0.0, 0.0]).longest_dry_spell_days == 2


def test_monthly_indicators_skips_missing_days_and_reports_how_many_had_data():
    m = one_month([5.0, NAN, 0.0], temps=[20.0, 22.0, NAN])
    assert m.days == 3
    assert m.rainfall_days == 2
    assert m.temperature_days == 2
    assert m.total_rainfall_mm == pytest.approx(5.0)
    assert m.mean_temperature_c == pytest.approx(21.0)


def test_monthly_indicators_month_without_data_is_none_not_zero():
    m = one_month([NAN, NAN], temps=[NAN, NAN])
    assert m.mean_temperature_c is None
    assert m.total_rainfall_mm is None
    assert m.dry_days is None
    assert m.longest_dry_spell_days is None
    assert m.extreme_rain_days is None


def test_monthly_indicators_without_extrema_never_report_heat_or_frost():
    # Means far above heat and below frost thresholds: still no claim without max/min.
    m = one_month([0.0, 0.0], temps=[40.0, -5.0])
    assert m.heat_stress_days is None
    assert m.frost_days is None
    assert m.extrema_days == 0


def test_monthly_indicators_counts_heat_and_frost_from_true_extrema():
    m = one_month(
        [0.0, 0.0, 0.0, 0.0],
        temperature_max_c=[35.0, 34.9, 36.0, NAN],
        temperature_min_c=[0.0, 0.1, -2.0, -3.0],
    )
    assert m.extrema_days == 3  # the 4th day has no max, so it is left out of both counts
    assert m.heat_stress_days == 2
    assert m.frost_days == 2


def test_monthly_indicators_splits_by_calendar_month_and_cuts_spells_at_the_edge():
    jan, feb = monthly_indicators(
        dates=days_from(date(2026, 1, 30), 4),  # Jan 30, Jan 31, Feb 1, Feb 2
        temperature_c=[20.0] * 4,
        rainfall_mm=[0.0, 0.0, 0.0, 0.0],
    )
    assert (jan.year, jan.month, jan.days, jan.longest_dry_spell_days) == (2026, 1, 2, 2)
    assert (feb.year, feb.month, feb.days, feb.longest_dry_spell_days) == (2026, 2, 2, 2)


def test_monthly_indicators_empty_series_gives_no_months():
    assert monthly_indicators(dates=[], temperature_c=[], rainfall_mm=[]) == ()


@pytest.mark.parametrize(
    ("kwargs", "match"),
    [
        ({"temperature_c": [20.0]}, "one value per date"),
        ({"temperature_max_c": [30.0, 30.0]}, "both temperature_max_c and temperature_min_c"),
        (
            {"temperature_max_c": [30.0], "temperature_min_c": [10.0]},
            "one value per date",
        ),
        ({"dates": [date(2026, 1, 2), date(2026, 1, 1)]}, "strictly increasing"),
        ({"dates": [date(2026, 1, 1), date(2026, 1, 1)]}, "strictly increasing"),
    ],
)
def test_monthly_indicators_rejects_misaligned_input(kwargs, match):
    args = {
        "dates": days_from(date(2026, 1, 1), 2),
        "temperature_c": [20.0, 20.0],
        "rainfall_mm": [0.0, 0.0],
        **kwargs,
    }
    with pytest.raises(DomainInvariantError, match=match):
        monthly_indicators(**args)


# ---------------------------------------------------------------- service

JAN = {"lat": 9.93, "lon": -84.08, "start": date(2026, 1, 1), "end": date(2026, 1, 31)}


class FixtureWeather:
    """Serves the real NASA POWER daily fixture (San José, Jan 2026) without HTTP or cache."""

    name = "nasa_power"

    def daily_weather(self, *, lat, lon, start, end):
        return parse_daily(load_fixture("nasa_power/daily_san_jose_202601.json"))


class ExtremaWeather:
    """Toy source that also returns true daily max / min columns."""

    name = "fake_extrema"

    def daily_weather(self, *, lat, lon, start, end):
        return pd.DataFrame(
            {
                "date": pd.date_range(start, periods=3, freq="D"),
                "temperature_c": [25.0, 26.0, 24.0],
                "rainfall_mm": [0.0, 40.0, 2.0],
                "temperature_max_c": [36.0, 30.0, 35.5],
                "temperature_min_c": [15.0, 16.0, 14.0],
            }
        )


def test_field_indicators_on_the_power_fixture():
    # Hand-checked on the fixture: 20 days < 1 mm, longest run Jan 19-29, wettest day 8.67 mm.
    (row,) = field_indicators(weather_source=FixtureWeather(), **JAN)
    assert row == {
        "year": 2026,
        "month": 1,
        "days": 31,
        "temperature_days": 31,
        "rainfall_days": 31,
        "extrema_days": 31,
        "mean_temperature_c": 22.44,
        "total_rainfall_mm": 35.2,
        "dry_days": 20,
        "longest_dry_spell_days": 11,
        "extreme_rain_days": 0,
        # Real T2M_MAX peaks at 28.03 °C and T2M_MIN bottoms at 17.33 °C this month:
        # no day reaches 35 °C or 0 °C, so both counts are a measured 0, not a missing value.
        "heat_stress_days": 0,
        "frost_days": 0,
    }


def test_field_indicators_skips_days_with_a_missing_extremum():
    raw = load_fixture("nasa_power/daily_san_jose_202601.json")
    raw["properties"]["parameter"]["T2M_MAX"]["20260110"] = -999.0
    raw["properties"]["parameter"]["T2M_MIN"]["20260120"] = -999.0

    class GappyWeather(FixtureWeather):
        def daily_weather(self, *, lat, lon, start, end):
            return parse_daily(raw)

    (row,) = field_indicators(weather_source=GappyWeather(), **JAN)
    assert row["extrema_days"] == 29
    assert row["temperature_days"] == 31
    assert row["heat_stress_days"] == 0


def test_field_indicators_counts_heat_and_frost_from_power_extrema_at_the_thresholds():
    # The real fixture has no hot or frosty day, so two days are pushed to the thresholds in the
    # test (not in the fixture) to exercise the POWER parse → indicator path end to end.
    raw = load_fixture("nasa_power/daily_san_jose_202601.json")
    raw["properties"]["parameter"]["T2M_MAX"]["20260102"] = 35.0  # == HEAT_STRESS_MAX_C counts
    raw["properties"]["parameter"]["T2M_MAX"]["20260103"] = 34.99  # just below: does not count
    raw["properties"]["parameter"]["T2M_MIN"]["20260104"] = 0.0  # == FROST_MIN_C counts

    class EdgeWeather(FixtureWeather):
        def daily_weather(self, *, lat, lon, start, end):
            return parse_daily(raw)

    (row,) = field_indicators(weather_source=EdgeWeather(), **JAN)
    assert row["heat_stress_days"] == 1
    assert row["frost_days"] == 1
    assert row["mean_temperature_c"] == pytest.approx(22.44)  # the mean is untouched


def test_field_indicators_keeps_fill_value_days_as_missing():
    raw = load_fixture("nasa_power/daily_san_jose_202601.json")
    raw["properties"]["parameter"]["PRECTOTCORR"]["20260131"] = -999.0  # the 8.67 mm day

    class GappyWeather(FixtureWeather):
        def daily_weather(self, *, lat, lon, start, end):
            return parse_daily(raw)

    (row,) = field_indicators(weather_source=GappyWeather(), **JAN)
    assert row["rainfall_days"] == 30
    assert row["total_rainfall_mm"] == pytest.approx(26.6)  # 35.24 - 8.67, rounded


def test_field_indicators_uses_extrema_columns_when_the_source_has_them():
    (row,) = field_indicators(weather_source=ExtremaWeather(), **JAN)
    assert row["extrema_days"] == 3
    assert row["heat_stress_days"] == 2
    assert row["frost_days"] == 0
    assert row["extreme_rain_days"] == 1


def test_field_indicators_works_offline_with_the_mock_source():
    rows = field_indicators(
        weather_source=MockClimate(),
        lat=9.93,
        lon=-84.08,
        start=date(2026, 1, 1),
        end=date(2026, 3, 31),
    )
    assert [r["month"] for r in rows] == [1, 2, 3]
    assert all(r["heat_stress_days"] is None for r in rows)
