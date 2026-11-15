"""NASA POWER daily history (IMERG rain, MERRA-2 temperature and wetness) for POST /plan-risk."""

from datetime import date

import httpx
import pandas as pd
import pytest
import respx

from app import services
from app.cache import JsonCache
from app.errors import CacheMissError, SourceDataError, SourceUnavailableError
from app.integrations.nasa_power import (
    DAILY_URL,
    HISTORY_PARAMETERS,
    NasaPowerClimate,
    parse_daily_history,
)
from app.settings import DataMode
from tests.conftest import load_fixture

# Real response, San Carlos (lat 11.0, lon -84.6), 2020-09-01 to 2020-11-30, time-standard=UTC.
FIXTURE = "nasa_power/daily_history_san_carlos_202009_202011.json"
FALL_2020 = {"lat": 11.0, "lon": -84.6, "start": date(2020, 9, 1), "end": date(2020, 11, 30)}
COLUMNS = [
    "date",
    "rainfall_mm",
    "rainfall_merra2_mm",
    "temperature_max_c",
    "temperature_min_c",
    "root_wetness",
]


def _set_all(raw: dict, param: str, value: float) -> None:
    for day in raw["properties"]["parameter"][param]:
        raw["properties"]["parameter"][param][day] = value


def test_parse_daily_history_real_response():
    df = parse_daily_history(load_fixture(FIXTURE))
    assert list(df.columns) == COLUMNS
    assert len(df) == 91  # Sep 1 .. Nov 30
    assert df["date"].iloc[0] == pd.Timestamp("2020-09-01")
    assert not df.isna().any().any()


def test_parse_daily_history_keeps_native_units():
    df = parse_daily_history(load_fixture(FIXTURE)).set_index("date")
    nov = df.loc["2020-11"]
    # Monthly sums of the native mm/day values (checked against the raw response).
    assert nov["rainfall_mm"].sum() == pytest.approx(328.4, abs=0.1)
    assert nov["rainfall_merra2_mm"].sum() == pytest.approx(1010.4, abs=0.1)


def test_parse_daily_history_wetness_is_a_fraction():
    df = parse_daily_history(load_fixture(FIXTURE))
    assert df["root_wetness"].between(0, 1).all()


def test_parse_daily_history_extrema_are_ordered():
    df = parse_daily_history(load_fixture(FIXTURE))
    assert (df["temperature_max_c"] >= df["temperature_min_c"]).all()


def test_parse_daily_history_fill_values_become_nan_for_that_variable_only():
    raw = load_fixture(FIXTURE)
    day = next(iter(raw["properties"]["parameter"]["IMERG_PRECTOT"]))
    raw["properties"]["parameter"]["IMERG_PRECTOT"][day] = -999.0
    df = parse_daily_history(raw)
    assert pd.isna(df["rainfall_mm"].iloc[0])
    assert df["rainfall_merra2_mm"].iloc[0] == pytest.approx(
        raw["properties"]["parameter"]["PRECTOTCORR"][day]
    )


@pytest.mark.parametrize("param", HISTORY_PARAMETERS)
def test_parse_daily_history_rejects_a_variable_without_data(param):
    # E.g. IMERG requested in local solar time: POWER answers 200 with only -999 fill values.
    raw = load_fixture(FIXTURE)
    _set_all(raw, param, -999.0)
    with pytest.raises(SourceDataError, match="has no data for") as exc:
        parse_daily_history(raw)
    assert exc.value.details["source"] == "nasa_power_daily_history"
    assert len(exc.value.details["empty_columns"]) == 1


@pytest.mark.parametrize(
    ("param", "unit"), [("IMERG_PRECTOT", "mm/hr"), ("GWETROOT", "%"), ("T2M_MAX", "K")]
)
def test_parse_daily_history_rejects_unexpected_units(param, unit):
    raw = load_fixture(FIXTURE)
    raw["parameters"][param]["units"] = unit
    with pytest.raises(SourceDataError, match=f"daily {param} is in") as exc:
        parse_daily_history(raw)
    assert exc.value.details == {"source": "nasa_power_daily_history", "parameter": param}


def test_parse_daily_history_rejects_a_missing_variable():
    raw = load_fixture(FIXTURE)
    del raw["properties"]["parameter"]["GWETROOT"]
    with pytest.raises(SourceDataError, match="Unexpected NASA POWER daily history payload"):
        parse_daily_history(raw)


def test_history_params_ask_for_utc_and_all_variables():
    params = NasaPowerClimate.history_request_params(
        11.001, -84.6, date(2001, 1, 1), date(2025, 12, 31)
    )
    assert params["time-standard"] == "UTC"
    assert params["parameters"] == "IMERG_PRECTOT,PRECTOTCORR,T2M_MAX,T2M_MIN,GWETROOT"
    assert params["latitude"] == 11.0
    assert (params["start"], params["end"]) == ("20010101", "20251231")


def test_history_cache_never_shares_keys_with_daily_weather(tmp_path):
    cache = JsonCache(tmp_path, DataMode.LIVE)
    args = (11.0, -84.6, FALL_2020["start"], FALL_2020["end"])
    history = cache.path_for(
        "nasa_power_daily_history", NasaPowerClimate.history_request_params(*args)
    )
    weather = cache.path_for("nasa_power_daily", NasaPowerClimate.daily_request_params(*args))
    assert history.parent.name != weather.parent.name


@respx.mock
def test_daily_history_fetches_and_caches(tmp_path):
    route = respx.get(DAILY_URL).mock(return_value=httpx.Response(200, json=load_fixture(FIXTURE)))
    live = NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE))
    assert len(live.daily_history(**FALL_2020)) == 91
    assert route.calls[0].request.url.params["time-standard"] == "UTC"

    offline = NasaPowerClimate(JsonCache(tmp_path, DataMode.CACHED))
    assert len(offline.daily_history(**FALL_2020)) == 91
    assert route.call_count == 1


@respx.mock
def test_daily_history_falls_back_to_cache_when_api_fails(tmp_path):
    respx.get(DAILY_URL).mock(
        side_effect=[httpx.Response(200, json=load_fixture(FIXTURE)), httpx.Response(500)]
    )
    src = NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE))
    src.daily_history(**FALL_2020)
    assert len(src.daily_history(**FALL_2020)) == 91  # 500 → cached copy


@respx.mock
def test_daily_history_bad_data_is_never_cached(tmp_path):
    raw = load_fixture(FIXTURE)
    _set_all(raw, "IMERG_PRECTOT", -999.0)
    respx.get(DAILY_URL).mock(return_value=httpx.Response(200, json=raw))
    cache = JsonCache(tmp_path, DataMode.LIVE)
    with pytest.raises(SourceDataError, match="has no data for"):
        NasaPowerClimate(cache).daily_history(**FALL_2020)
    args = (11.0, -84.6, FALL_2020["start"], FALL_2020["end"])
    assert not cache.path_for(
        "nasa_power_daily_history", NasaPowerClimate.history_request_params(*args)
    ).exists()


@respx.mock
def test_daily_history_http_error_without_cache_is_source_unavailable(tmp_path):
    respx.get(DAILY_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(SourceUnavailableError, match="HTTP 503"):
        NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE)).daily_history(**FALL_2020)


def test_daily_history_cached_mode_miss(tmp_path):
    with pytest.raises(CacheMissError, match="nasa_power_daily_history") as exc:
        NasaPowerClimate(JsonCache(tmp_path, DataMode.CACHED)).daily_history(**FALL_2020)
    assert exc.value.details == {"source": "nasa_power_daily_history"}


@pytest.mark.network
def test_real_daily_history_has_imerg_rain(tmp_path):
    """Calls the real API. Run with `make test-all`. Not part of CI."""
    df = NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE)).daily_history(**FALL_2020)
    assert len(df) == 91
    assert df["rainfall_mm"].notna().all()


# ---------------------------------------------------------------- services: history → plan-risk
def _history_frame(columns: list[str]) -> pd.DataFrame:
    days = pd.date_range("2000-06-01", "2000-06-10", freq="D")
    return pd.DataFrame({"date": days, **{c: [1.0] * len(days) for c in columns}})


def test_history_without_merra2_rain_is_bad_data_not_a_crash():
    """The service reads rainfall_merra2_mm too (rain-source gap): a 502, never a KeyError."""
    df = _history_frame(["rainfall_mm", "temperature_max_c", "temperature_min_c", "root_wetness"])
    with pytest.raises(SourceDataError, match="rainfall_merra2_mm") as exc:
        services._daily_history(df, date(2000, 6, 1), date(2000, 6, 10), "nasa_power")
    assert exc.value.details == {"source": "nasa_power"}


@pytest.mark.parametrize(
    ("merra2_per_day", "en", "es"),
    [
        (1.2, "20% more rain here", "20 % más lluvia aquí"),
        (0.7, "30% less rain here", "30 % menos lluvia aquí"),
        (3.1, "more than twice as much rain here", "más del doble de lluvia aquí"),
    ],
)
def test_rain_source_gap_caps_large_differences_in_words(merra2_per_day, en, es):
    df = _history_frame(["rainfall_mm"])
    df["rainfall_merra2_mm"] = merra2_per_day
    gap = services._rain_source_gap(df)
    assert gap is not None
    assert en in gap.en
    assert es in gap.es
