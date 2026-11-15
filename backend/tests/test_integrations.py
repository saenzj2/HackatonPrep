import csv
import io
from datetime import date

import httpx
import pandas as pd
import pytest
import respx
from pydantic import SecretStr

from app.cache import JsonCache
from app.domain.models import level_for
from app.domain.rotation_rules import judge_transition
from app.errors import (
    CacheMissError,
    ConfigError,
    ErrorCode,
    SourceDataError,
    SourceUnavailableError,
)
from app.integrations import build_sources
from app.integrations.base import (
    ClimateSource,
    CropSource,
    DailyWeatherSource,
    SoilSource,
    TerrainSource,
)
from app.integrations.ecocrop import EcoCropCatalog
from app.integrations.mock import MockClimate, MockSoil, MockTerrain
from app.integrations.nasa_power import (
    BASE_URL,
    DAILY_URL,
    NasaPowerClimate,
    parse_climatology,
    parse_daily,
)
from app.integrations.opentopography import BASE_URL as OT_URL
from app.integrations.opentopography import (
    OpenTopographyElevation,
    parse_elevation,
    snap_to_srtm_grid,
)
from app.settings import BACKEND_DIR, DataMode, EnvSettings
from tests.conftest import load_fixture

POWER_FIXTURE = "nasa_power/climatology_alajuela.json"  # real response, lat 10.0 lon -84.2
# real response, lat 9.93 lon -84.08, Jan 2026
DAILY_FIXTURE = "nasa_power/daily_san_jose_202601.json"


# ---------------------------------------------------------------- NASA POWER (template)
def test_parse_real_power_response():
    climate = parse_climatology(load_fixture(POWER_FIXTURE))
    assert climate.temperature_c[0] == 22.66  # JAN T2M, °C
    assert climate.rainfall_mm[0] == pytest.approx(1.22 * 31, abs=0.1)  # mm/day → mm/month
    assert climate.rainfall_mm[9] > climate.rainfall_mm[1]  # Oct (wet) > Feb (dry)


def test_parse_reads_daily_max_and_min():
    climate = parse_climatology(load_fixture(POWER_FIXTURE))
    assert climate.temperature_max_c[0] == 31.3  # JAN T2M_MAX, mean daily max °C
    assert climate.temperature_min_c[0] == 16.11  # JAN T2M_MIN, mean daily min °C


@pytest.mark.parametrize("param", ["T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR"])
def test_parse_rejects_fill_values(param):
    raw = load_fixture(POWER_FIXTURE)
    raw["properties"]["parameter"][param]["MAR"] = -999.0
    with pytest.raises(SourceDataError, match="fill values"):
        parse_climatology(raw)


def test_parse_rejects_unexpected_payload():
    with pytest.raises(SourceDataError, match="Unexpected NASA POWER payload") as exc:
        parse_climatology({"messages": ["boom"]})
    assert exc.value.code == ErrorCode.SOURCE_BAD_DATA


@respx.mock
def test_live_mode_fetches_and_caches(tmp_path):
    route = respx.get(BASE_URL).mock(
        return_value=httpx.Response(200, json=load_fixture(POWER_FIXTURE))
    )
    live = NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE))
    assert live.monthly_climate(10.0, -84.2).temperature_c[0] == 22.66
    assert route.called
    assert route.calls[0].request.url.params["community"] == "AG"

    # Same data now available offline
    offline = NasaPowerClimate(JsonCache(tmp_path, DataMode.CACHED))
    assert offline.monthly_climate(10.0, -84.2).temperature_c[0] == 22.66
    assert route.call_count == 1


@respx.mock
def test_live_mode_falls_back_to_cache_when_api_fails(tmp_path):
    respx.get(BASE_URL).mock(
        side_effect=[httpx.Response(200, json=load_fixture(POWER_FIXTURE)), httpx.Response(500)]
    )
    src = NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE))
    src.monthly_climate(10.0, -84.2)
    assert src.monthly_climate(10.0, -84.2).temperature_c[0] == 22.66  # 500 → cached copy


@respx.mock
def test_live_mode_raises_without_cache(tmp_path):
    respx.get(BASE_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(SourceUnavailableError, match="HTTP 503") as exc:
        NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE)).monthly_climate(10.0, -84.2)
    assert exc.value.details == {"source": "nasa_power", "status": 503}


@respx.mock
def test_network_failure_is_source_unavailable_without_url(tmp_path):
    respx.get(BASE_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))
    with pytest.raises(SourceUnavailableError, match="ConnectTimeout") as exc:
        NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE)).monthly_climate(10.0, -84.2)
    assert "http" not in exc.value.message.lower()  # never leak URLs (could carry API keys)


@respx.mock
def test_non_json_body_is_bad_data(tmp_path):
    respx.get(BASE_URL).mock(return_value=httpx.Response(200, text="<html>maintenance</html>"))
    with pytest.raises(SourceDataError, match="non-JSON"):
        NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE)).monthly_climate(10.0, -84.2)


@respx.mock
def test_bad_data_never_overwrites_a_good_cache(tmp_path):
    good = load_fixture(POWER_FIXTURE)
    bad = load_fixture(POWER_FIXTURE)
    bad["properties"]["parameter"]["T2M"]["JAN"] = -999.0
    respx.get(BASE_URL).mock(
        side_effect=[httpx.Response(200, json=good), httpx.Response(200, json=bad)]
    )
    cache = JsonCache(tmp_path, DataMode.LIVE)
    src = NasaPowerClimate(cache)
    src.monthly_climate(10.0, -84.2)
    file = cache.path_for("nasa_power", src.request_params(10.0, -84.2))
    before = file.read_text()
    assert src.monthly_climate(10.0, -84.2).temperature_c[0] == 22.66  # served the good copy
    assert file.read_text() == before


def test_corrupt_cache_file_is_a_miss(tmp_path):
    cache = JsonCache(tmp_path, DataMode.CACHED)
    params = NasaPowerClimate.request_params(10.0, -84.2)
    path = cache.path_for("nasa_power", params)
    path.parent.mkdir(parents=True)
    path.write_text('{"data": {"trunc')  # e.g. process killed mid-write
    with pytest.raises(CacheMissError):
        NasaPowerClimate(cache).monthly_climate(10.0, -84.2)


@respx.mock
def test_cache_write_leaves_no_temp_files(tmp_path):
    respx.get(BASE_URL).mock(return_value=httpx.Response(200, json=load_fixture(POWER_FIXTURE)))
    NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE)).monthly_climate(10.0, -84.2)
    files = [p.name for p in tmp_path.rglob("*") if p.is_file()]
    assert len(files) == 1
    assert files[0].endswith(".json")


def test_cached_mode_miss(tmp_path):
    with pytest.raises(CacheMissError, match="data_mode=live"):
        NasaPowerClimate(JsonCache(tmp_path, DataMode.CACHED)).monthly_climate(10.0, -84.2)


@pytest.mark.network
def test_real_power_api(tmp_path):
    """Calls the real API. Run with `make test-all`. Not part of CI."""
    climate = NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE)).monthly_climate(10.0, -84.2)
    assert 10 < climate.temperature_c[0] < 35


# ---------------------------------------------------------------- NASA POWER daily
JAN_2026 = {"lat": 9.93, "lon": -84.08, "start": date(2026, 1, 1), "end": date(2026, 1, 31)}


def test_parse_daily_real_response():
    df = parse_daily(load_fixture(DAILY_FIXTURE))
    assert list(df.columns) == ["date", "temperature_c", "rainfall_mm"]
    assert len(df) == 31
    assert df["date"].iloc[0] == pd.Timestamp("2026-01-01")
    assert df["temperature_c"].iloc[0] == pytest.approx(22.43)  # T2M, °C
    assert df["rainfall_mm"].iloc[-1] == pytest.approx(8.67)  # PRECTOTCORR, mm/day as is


def test_parse_daily_turns_fill_values_into_nan():
    raw = load_fixture(DAILY_FIXTURE)
    raw["properties"]["parameter"]["PRECTOTCORR"]["20260105"] = -999.0
    df = parse_daily(raw)
    assert pd.isna(df.loc[4, "rainfall_mm"])
    assert df.loc[4, "temperature_c"] == pytest.approx(22.19)  # the other variable is kept


def test_parse_daily_aligns_rows_by_date():
    raw = load_fixture(DAILY_FIXTURE)
    rain = raw["properties"]["parameter"]["PRECTOTCORR"]
    raw["properties"]["parameter"]["PRECTOTCORR"] = dict(reversed(list(rain.items())))
    df = parse_daily(raw)
    assert df["rainfall_mm"].iloc[-1] == pytest.approx(8.67)  # still Jan 31


def test_parse_daily_rejects_all_fill_values():
    raw = load_fixture(DAILY_FIXTURE)
    for series in raw["properties"]["parameter"].values():
        for day in series:
            series[day] = -999.0
    with pytest.raises(SourceDataError, match="only fill values"):
        parse_daily(raw)


@pytest.mark.parametrize(
    "raw",
    [
        {"messages": ["boom"]},
        {"properties": {"parameter": {"T2M": {"2026-01-01": 22.0}, "PRECTOTCORR": {}}}},
        {"properties": {"parameter": {"T2M": {"20260101": "hot"}, "PRECTOTCORR": {}}}},
    ],
    ids=["missing_keys", "bad_date", "non_numeric"],
)
def test_parse_daily_rejects_unexpected_payload(raw):
    with pytest.raises(SourceDataError, match="Unexpected NASA POWER daily payload") as exc:
        parse_daily(raw)
    assert exc.value.details == {"source": "nasa_power_daily"}


@respx.mock
def test_daily_weather_fetches_and_caches(tmp_path):
    route = respx.get(DAILY_URL).mock(
        return_value=httpx.Response(200, json=load_fixture(DAILY_FIXTURE))
    )
    live = NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE))
    assert len(live.daily_weather(**JAN_2026)) == 31
    sent = route.calls[0].request.url.params
    assert sent["start"] == "20260101"
    assert sent["end"] == "20260131"

    offline = NasaPowerClimate(JsonCache(tmp_path, DataMode.CACHED))
    assert len(offline.daily_weather(**JAN_2026)) == 31
    assert route.call_count == 1


@respx.mock
def test_daily_weather_http_error_is_source_unavailable(tmp_path):
    respx.get(DAILY_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(SourceUnavailableError, match="HTTP 503"):
        NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE)).daily_weather(**JAN_2026)


def test_daily_weather_cached_mode_miss(tmp_path):
    with pytest.raises(CacheMissError, match="data_mode=live"):
        NasaPowerClimate(JsonCache(tmp_path, DataMode.CACHED)).daily_weather(**JAN_2026)


@pytest.mark.network
def test_real_power_daily_api(tmp_path):
    """Calls the real API. Run with `make test-all`. Not part of CI."""
    df = NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE)).daily_weather(**JAN_2026)
    assert len(df) == 31


# ---------------------------------------------------------------- OpenTopography (SRTM GL1)
OT_KEY = SecretStr("test-key-not-real")
# Real responses around lat 9.93 lon -84.08 (San José), one SRTM sample (1 arc-second) apart
OT_POINTS = ("center", "north", "south", "east", "west")


def ot_fixture(point):
    return load_fixture(f"opentopography/elevation_san_jose_{point}.json")


def ot_responder(request):
    """Serve the saved real response whose Location matches the requested lat/lon."""
    lat = float(request.url.params["latitude"])
    lon = float(request.url.params["longitude"])
    for point in OT_POINTS:
        raw = ot_fixture(point)
        if (raw["Location"]["Latitude"], raw["Location"]["Longitude"]) == (lat, lon):
            return httpx.Response(200, json=raw)
    return httpx.Response(404, json={"Status": "Error"})


def ot_source(tmp_path, mode=DataMode.LIVE, key=OT_KEY):
    return OpenTopographyElevation(JsonCache(tmp_path, mode), key)


def test_parse_real_elevation_response():
    assert parse_elevation(ot_fixture("center")) == 1164.0  # metres, as is


def test_parse_elevation_rejects_srtm_void():
    raw = ot_fixture("center")
    raw["Elevation"] = -32768
    with pytest.raises(SourceDataError, match="data void"):
        parse_elevation(raw)


def test_parse_elevation_rejects_failed_status():
    with pytest.raises(SourceDataError, match="could not return an elevation") as exc:
        parse_elevation({"Status": "Error", "Message": "Point outside dataset"})
    assert exc.value.details == {"source": "opentopography"}


@pytest.mark.parametrize("bad", [None, "high", {}])
def test_parse_elevation_rejects_non_numeric(bad):
    raw = ot_fixture("center")
    raw["Elevation"] = bad
    with pytest.raises(SourceDataError, match="Unexpected OpenTopography payload"):
        parse_elevation(raw)


def test_snap_to_srtm_grid_rounds_to_whole_arc_seconds():
    assert snap_to_srtm_grid(9.93012) == 9.93  # 35748.4 arc-seconds -> 35748
    assert snap_to_srtm_grid(-84.08) == -84.08


@respx.mock
def test_terrain_sample_fetches_five_points_and_caches(tmp_path):
    route = respx.get(OT_URL).mock(side_effect=ot_responder)
    sample = ot_source(tmp_path).terrain_sample(9.93, -84.08)
    assert route.call_count == 5
    assert (sample.elevation_m, sample.north_m, sample.south_m) == (1164.0, 1164.0, 1165.0)
    assert (sample.east_m, sample.west_m) == (1164.0, 1163.0)
    assert route.calls[0].request.url.params["dataset"] == "SRTM_GL1"

    offline = ot_source(tmp_path, DataMode.CACHED, key=None)  # no key needed once cached
    assert offline.terrain_sample(9.93, -84.08) == sample
    assert route.call_count == 5


@respx.mock
def test_terrain_sample_repeat_in_live_mode_uses_the_cache(tmp_path):
    # SRTM never changes: a second live call must not spend the key's daily quota again
    route = respx.get(OT_URL).mock(side_effect=ot_responder)
    src = ot_source(tmp_path)
    first = src.terrain_sample(9.93, -84.08)
    assert src.terrain_sample(9.93, -84.08) == first
    assert route.call_count == 5  # not 10


def any_point_responder(request):
    """A real response shape for whatever point was asked (Location echoed like the API does)."""
    lat = float(request.url.params["latitude"])
    lon = float(request.url.params["longitude"])
    raw = ot_fixture("center") | {"Location": {"Latitude": lat, "Longitude": lon}}
    return httpx.Response(200, json=raw)


@respx.mock
def test_neighbour_cache_keys_match_the_next_location(tmp_path):
    # One arc-second north, the old north neighbour is the new centre and the old centre the new
    # south neighbour: same cache keys, so only 3 new requests instead of 5.
    route = respx.get(OT_URL).mock(side_effect=any_point_responder)
    src = ot_source(tmp_path)
    src.terrain_sample(9.93, -84.08)
    src.terrain_sample(9.93 + 1 / 3600, -84.08)
    assert route.call_count == 8
    first_north = route.calls[1].request.url.params["latitude"]
    second_centre = OpenTopographyElevation.point_params(snap_to_srtm_grid(9.93 + 1 / 3600), 0)
    assert float(first_north) == second_centre["latitude"]


@respx.mock
def test_daily_quota_reached_has_a_clear_message(tmp_path):
    respx.get(OT_URL).mock(return_value=httpx.Response(429))
    with pytest.raises(SourceUnavailableError, match="daily request limit") as exc:
        ot_source(tmp_path).elevation_m(9.93, -84.08)
    assert exc.value.details == {"source": "opentopography", "status": 429}


@respx.mock
def test_terrain_sample_spacing_is_in_metres(tmp_path):
    respx.get(OT_URL).mock(side_effect=ot_responder)
    sample = ot_source(tmp_path).terrain_sample(9.93, -84.08)
    assert sample.spacing_ns_m == pytest.approx(30.89, abs=0.01)  # 1 arc-second of latitude
    assert sample.spacing_ew_m == pytest.approx(30.42, abs=0.01)  # same x cos(9.93 deg)


@respx.mock
def test_api_key_is_sent_but_never_cached(tmp_path):
    route = respx.get(OT_URL).mock(side_effect=ot_responder)
    ot_source(tmp_path).elevation_m(9.93, -84.08)
    assert route.calls[0].request.url.params["API_Key"] == "test-key-not-real"
    cached = [p.read_text() for p in tmp_path.rglob("*.json")]
    assert len(cached) == 1
    assert "test-key-not-real" not in cached[0]


@respx.mock
def test_http_error_never_leaks_the_key(tmp_path):
    respx.get(OT_URL).mock(return_value=httpx.Response(401, text="Invalid API key"))
    with pytest.raises(SourceUnavailableError, match="HTTP 401") as exc:
        ot_source(tmp_path).elevation_m(9.93, -84.08)
    assert exc.value.details == {"source": "opentopography", "status": 401}
    assert exc.value.__cause__ is None  # no httpx error (its message has the URL) chained
    assert "test-key-not-real" not in str(exc.value)


@respx.mock
def test_network_failure_never_leaks_the_key(tmp_path):
    respx.get(OT_URL).mock(side_effect=httpx.ConnectTimeout("timed out"))
    with pytest.raises(SourceUnavailableError, match="ConnectTimeout") as exc:
        ot_source(tmp_path).elevation_m(9.93, -84.08)
    assert "test-key-not-real" not in str(exc.value)


def test_missing_key_in_live_mode_is_config_error(tmp_path):
    with pytest.raises(ConfigError, match="OPEN_TOPOGRAPHY_KEY"):
        ot_source(tmp_path, key=None).elevation_m(9.93, -84.08)


@respx.mock
def test_void_elevation_is_never_cached(tmp_path):
    void = ot_fixture("center") | {"Elevation": -32768}
    respx.get(OT_URL).mock(return_value=httpx.Response(200, json=void))
    with pytest.raises(SourceDataError, match="data void"):
        ot_source(tmp_path).elevation_m(9.93, -84.08)
    assert not list(tmp_path.rglob("*.json"))


def test_elevation_cached_mode_miss(tmp_path):
    with pytest.raises(CacheMissError, match="data_mode=live"):
        ot_source(tmp_path, DataMode.CACHED).elevation_m(9.93, -84.08)


@pytest.mark.network
def test_real_opentopography_api(tmp_path):
    """Real API: uses 5 of the key's ~50 daily calls. Needs OPEN_TOPOGRAPHY_KEY in backend/.env."""
    key = EnvSettings().open_topography_key
    if key is None:
        pytest.skip("OPEN_TOPOGRAPHY_KEY not set")
    sample = ot_source(tmp_path, key=key).terrain_sample(9.93, -84.08)
    assert 1000 < sample.elevation_m < 1300


# ---------------------------------------------------------------- EcoCrop
def test_ecocrop_catalog_loads():
    crops = EcoCropCatalog(BACKEND_DIR / "data" / "ecocrop_subset.csv").all()
    assert {"rice", "beans", "maize"} <= set(crops)
    assert crops["beans"].is_legume
    assert not crops["maize"].is_legume


def test_ecocrop_bad_row(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("id,name\nrice,Rice\n")
    with pytest.raises(ConfigError, match="line 2") as exc:
        EcoCropCatalog(bad).all()
    assert exc.value.details["source"] == "ecocrop_subset"


def _catalog_with(tmp_path, *rows: str) -> EcoCropCatalog:
    real = (BACKEND_DIR / "data" / "ecocrop_subset.csv").read_text().splitlines()
    path = tmp_path / "crops.csv"
    path.write_text("\n".join([real[0], *rows]) + "\n")
    return EcoCropCatalog(path)


def test_ecocrop_short_row_is_config_error(tmp_path):
    with pytest.raises(ConfigError, match="line 2"):
        _catalog_with(tmp_path, "rice,Rice,Oryza sativa").all()


def test_ecocrop_duplicate_id_is_config_error(tmp_path):
    real_row = (BACKEND_DIR / "data" / "ecocrop_subset.csv").read_text().splitlines()[1]
    with pytest.raises(ConfigError, match="duplicate crop id"):
        _catalog_with(tmp_path, real_row, real_row).all()


def test_ecocrop_catalog_reads_crop_traits():
    crops = EcoCropCatalog(BACKEND_DIR / "data" / "ecocrop_subset.csv").all()
    cowpea = crops["cowpea"]
    assert cowpea.is_cover_crop
    assert cowpea.nitrogen_demand == pytest.approx(0.33)
    assert cowpea.root_depth_m == pytest.approx(1.0)
    assert cowpea.sources


def test_ecocrop_every_crop_has_sources_and_market_note():
    for crop in EcoCropCatalog(BACKEND_DIR / "data" / "ecocrop_subset.csv").all().values():
        assert crop.sources, crop.id
        assert crop.market_note, crop.id


def _real_row_with(column: str, value: str) -> str:
    """The first real CSV row with one column replaced (csv-aware, values may contain commas)."""
    lines = (BACKEND_DIR / "data" / "ecocrop_subset.csv").read_text().splitlines()
    header, row = next(csv.reader(lines[:1])), next(csv.reader(lines[1:2]))
    row[header.index(column)] = value
    out = io.StringIO()
    csv.writer(out, lineterminator="").writerow(row)
    return out.getvalue()


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("forage_value", "lots"),
        ("nitrogen_demand", ""),
        ("nutrition_density", "1.5"),
        ("mycorrhizal_affinity", "high"),
        ("root_depth_m", "0"),
        ("root_depth_m", "deep"),
        ("sources", " ; "),
    ],
)
def test_ecocrop_bad_trait_is_config_error(tmp_path, column, value):
    with pytest.raises(ConfigError, match="line 2"):
        _catalog_with(tmp_path, _real_row_with(column, value)).all()


def test_fungi_break_fires_with_real_crops():
    """#24 reminder: skipped until the catalog has a mycorrhizal non-host (e.g. amaranth)."""
    crops = EcoCropCatalog(BACKEND_DIR / "data" / "ecocrop_subset.csv").all().values()
    non_hosts = [c for c in crops if level_for(c.mycorrhizal_affinity) == "none"]
    dependents = [c for c in crops if level_for(c.mycorrhizal_affinity) == "high"]
    if not non_hosts or not dependents:
        pytest.skip("#24: add a mycorrhizal non-host crop so fungi_break is tested on real data")
    rules = [h.rule for h in judge_transition(non_hosts[0], dependents[0]).hits]
    assert "fungi_break" in rules


# ---------------------------------------------------------------- mock + protocols
def test_mock_is_deterministic_and_location_dependent():
    a, b = MockClimate().monthly_climate(10, -84), MockClimate().monthly_climate(10, -84)
    assert a == b
    assert a != MockClimate().monthly_climate(9, -83)
    assert 4.5 < MockSoil().soil(10, -84).ph < 7.5


def test_mock_terrain_is_deterministic_with_slope_0_to_25_pct():
    a, b = MockTerrain().terrain_sample(10, -84), MockTerrain().terrain_sample(10, -84)
    assert a == b
    rise_m = a.east_m - a.west_m
    assert 0 <= 100 * rise_m / (2 * a.spacing_ew_m) <= 25


def test_mock_daily_weather_matches_power_columns():
    period = {"lat": 10, "lon": -84, "start": date(2026, 1, 1), "end": date(2026, 1, 31)}
    df = MockClimate().daily_weather(**period)
    assert list(df.columns) == ["date", "temperature_c", "rainfall_mm"]
    assert len(df) == 31
    assert (df["rainfall_mm"] >= 0).all()
    assert df.equals(MockClimate().daily_weather(**period))  # deterministic


def test_build_sources_mock_mode_has_erosion_sources(config, env):
    sources = build_sources(config, env)  # conftest forces mock mode
    assert isinstance(sources.daily, MockClimate)
    assert isinstance(sources.terrain, MockTerrain)
    assert set(sources.names()) == {"climate", "soil", "crops"}  # API contract unchanged


def test_build_sources_live_mode_uses_real_erosion_sources(config, env):
    sources = build_sources(config.model_copy(update={"data_mode": DataMode.LIVE}), env)
    assert isinstance(sources.daily, NasaPowerClimate)
    assert isinstance(sources.terrain, OpenTopographyElevation)


def test_adapters_implement_protocols(tmp_path):
    assert isinstance(MockClimate(), ClimateSource)
    assert isinstance(NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE)), ClimateSource)
    assert isinstance(MockSoil(), SoilSource)
    assert isinstance(EcoCropCatalog(tmp_path / "x.csv"), CropSource)
    assert isinstance(NasaPowerClimate(JsonCache(tmp_path, DataMode.LIVE)), DailyWeatherSource)
    assert isinstance(ot_source(tmp_path, key=None), TerrainSource)
    assert isinstance(MockClimate(), DailyWeatherSource)
    assert isinstance(MockTerrain(), TerrainSource)
