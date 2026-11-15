"""OpenLandMap / Earth Engine soil adapter: parsing real fixtures, caching, error translation.

Earth Engine is never called here: tests inject a fake `sampler`, or patch `ee.Initialize`.
The one real request is marked @pytest.mark.network.
"""

import json

import ee
import pytest
from google.auth.exceptions import RefreshError

from app.cache import JsonCache
from app.domain.models import SoilProfile
from app.errors import CacheMissError, ConfigError, SourceDataError, SourceUnavailableError
from app.integrations import build_sources, openlandmap
from app.integrations.base import SoilProfileSource
from app.integrations.mock import MockSoilProfile
from app.integrations.openlandmap import (
    DEPTHS_CM,
    USDA_TEXTURE_CLASSES,
    EarthEngineSoil,
    initialize_earth_engine,
    parse_soil_profile,
    snap_to_pixel_center,
)
from app.settings import DEFAULT_GEE_PROJECT_ID, DataMode, EnvSettings, get_env
from tests.conftest import load_fixture

SAN_JOSE = (9.93, -84.08)  # fixture point (docs/sources/openlandmap.md)


def san_jose():
    return load_fixture("openlandmap/soil_san_jose.json")


def parse(raw):
    return parse_soil_profile(raw, lat=SAN_JOSE[0], lon=SAN_JOSE[1])


class FakeSampler:
    """Stands in for the Earth Engine request; counts calls."""

    def __init__(self, result=None, error=None):
        self.result = san_jose() if result is None else result
        self.error = error
        self.calls = []

    def __call__(self, lat, lon):
        self.calls.append((lat, lon))
        if self.error is not None:
            raise self.error
        return self.result


def soil_source(tmp_path, mode=DataMode.LIVE, sampler=None, project_id="test-project"):
    return EarthEngineSoil(
        JsonCache(tmp_path, mode), project_id=project_id, sampler=sampler or FakeSampler()
    )


# ---------------------------------------------------------------- parsing
def test_parse_converts_stored_integers_to_physical_units():
    top = parse(san_jose()).layers[0]
    assert top.depth_cm == 0
    assert top.ph == pytest.approx(6.6)  # stored 66, pH x 10
    assert top.organic_carbon_g_kg == pytest.approx(10.0)  # stored 2, steps of 5 g/kg
    assert top.clay_pct == pytest.approx(38.0)
    assert top.sand_pct == pytest.approx(34.0)
    assert top.bulk_density_kg_m3 == pytest.approx(1270.0)  # stored 127, steps of 10 kg/m³
    assert top.field_capacity_m3m3 == pytest.approx(0.34)  # stored 34 volumetric %
    assert top.texture_class == "clay loam"  # code 4


def test_parse_derives_silt_from_clay_and_sand():
    assert parse(san_jose()).layers[0].silt_pct == pytest.approx(28.0)  # 100 - 38 - 34


def test_parse_returns_one_layer_per_depth_shallowest_first():
    assert [layer.depth_cm for layer in parse(san_jose()).layers] == [0, 10, 30]


def test_parse_masked_pixels_become_none_not_an_error():
    profile = parse(load_fixture("openlandmap/soil_pacific_ocean.json"))
    for layer in profile.layers:
        assert layer.ph is None
        assert layer.silt_pct is None
        assert layer.texture_class is None


def test_parse_silt_is_none_when_only_one_fraction_is_masked():
    raw = san_jose() | {"sand_b0": None}
    top = parse(raw).layers[0]
    assert top.sand_pct is None
    assert top.silt_pct is None
    assert top.clay_pct == pytest.approx(38.0)


def test_parse_silt_is_none_when_clay_and_sand_exceed_100_pct():
    top = parse(san_jose() | {"clay_b0": 60, "sand_b0": 50}).layers[0]
    assert top.silt_pct is None


@pytest.mark.parametrize(
    ("band", "value", "match"),
    [
        ("clay_b0", 150, "clay at 0 cm is 150"),
        ("ph_b10", 200, "ph at 10 cm"),
        ("clay_b0", "38", "expected a number"),
        ("clay_b0", True, "expected a number"),
        ("texture_class_b30", 13, "Unknown USDA texture class"),
        ("texture_class_b0", 4.5, "Unknown USDA texture class"),
    ],
)
def test_parse_rejects_impossible_values(band, value, match):
    with pytest.raises(SourceDataError, match=match) as exc:
        parse(san_jose() | {band: value})
    assert exc.value.details == {"source": "openlandmap"}


def test_parse_rejects_missing_band():
    raw = san_jose()
    del raw["bulk_density_b30"]
    with pytest.raises(SourceDataError, match="no bulk_density_b30 band"):
        parse(raw)


def test_texture_classes_cover_the_12_usda_codes():
    assert sorted(USDA_TEXTURE_CLASSES) == list(range(1, 13))


# ---------------------------------------------------------------- grid + cache keys
def test_snap_to_pixel_center_of_the_250m_grid():
    assert snap_to_pixel_center(*SAN_JOSE) == (9.929375, -84.080208)


def test_points_in_one_pixel_share_a_cache_key():
    a = EarthEngineSoil.point_params(9.93, -84.08)
    assert a == EarthEngineSoil.point_params(9.9301, -84.0799)
    assert a != EarthEngineSoil.point_params(9.93, -84.077)  # next pixel east (~230 m)


def test_cache_key_names_assets_and_depths_but_no_credentials():
    params = EarthEngineSoil.point_params(*SAN_JOSE)
    assert set(params) == {"assets", "depths_cm", "latitude", "longitude"}
    assert params["depths_cm"] == list(DEPTHS_CM)
    assert len(params["assets"]) == 7


# ---------------------------------------------------------------- adapter + cache
def test_soil_profile_samples_the_pixel_center(tmp_path):
    sampler = FakeSampler()
    profile = soil_source(tmp_path, sampler=sampler).soil_profile(*SAN_JOSE)
    assert isinstance(profile, SoilProfile)
    assert sampler.calls == [(9.929375, -84.080208)]


def test_soil_profile_live_reuses_cached_pixel_without_new_request(tmp_path):
    sampler = FakeSampler()
    source = soil_source(tmp_path, sampler=sampler)
    first = source.soil_profile(*SAN_JOSE)
    assert source.soil_profile(9.9301, -84.0801) == first
    assert len(sampler.calls) == 1  # the maps are static: one request per pixel, ever


def test_soil_profile_cached_mode_works_without_earth_engine(tmp_path):
    soil_source(tmp_path).soil_profile(*SAN_JOSE)  # fill the cache in live mode
    offline = EarthEngineSoil(JsonCache(tmp_path, DataMode.CACHED), project_id=None)
    assert offline.soil_profile(*SAN_JOSE).layers[0].texture_class == "clay loam"


def test_soil_profile_cached_mode_miss(tmp_path):
    sampler = FakeSampler()
    with pytest.raises(CacheMissError, match="openlandmap"):
        soil_source(tmp_path, DataMode.CACHED, sampler).soil_profile(*SAN_JOSE)
    assert sampler.calls == []


def test_soil_profile_bad_answer_is_never_cached(tmp_path):
    source = soil_source(tmp_path, sampler=FakeSampler(san_jose() | {"clay_b0": 150}))
    with pytest.raises(SourceDataError, match="clay"):
        source.soil_profile(*SAN_JOSE)
    assert source.cache.peek("openlandmap", source.point_params(*SAN_JOSE)) is None


@pytest.mark.parametrize(
    ("error", "expected", "match"),
    [
        (ee.EEException("Too many concurrent aggregations"), SourceUnavailableError, "failed"),
        (TimeoutError("timed out"), SourceUnavailableError, "unreachable"),
        (RefreshError("invalid_grant"), ConfigError, "earthengine authenticate"),
    ],
)
def test_fetch_translates_earth_engine_errors(tmp_path, error, expected, match):
    source = soil_source(tmp_path, sampler=FakeSampler(error=error))
    with pytest.raises(expected, match=match) as exc:
        source.soil_profile(*SAN_JOSE)
    assert exc.value.details == {"source": "openlandmap"}
    assert exc.value.__cause__ is error


def test_fetch_rejects_non_object_answer(tmp_path):
    source = soil_source(tmp_path, sampler=FakeSampler(result=[1, 2]))
    with pytest.raises(SourceDataError, match="returned list"):
        source.soil_profile(*SAN_JOSE)


def test_missing_project_id_is_config_error_naming_the_variable(tmp_path):
    source = EarthEngineSoil(JsonCache(tmp_path, DataMode.LIVE), project_id=None)
    with pytest.raises(ConfigError, match="GEE_PROJECT_ID"):
        source.soil_profile(*SAN_JOSE)


# ---------------------------------------------------------------- Earth Engine initialization
@pytest.fixture
def fake_ee(monkeypatch):
    """Records ee.Initialize calls instead of contacting Google; fresh 'initialized' state."""
    calls = []
    monkeypatch.setattr(openlandmap, "_initialized_projects", set())
    monkeypatch.setattr(ee, "Initialize", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(ee.data, "setDeadline", lambda ms: None)
    return calls


def test_initialize_earth_engine_runs_once_per_process(fake_ee):
    initialize_earth_engine("test-project")
    initialize_earth_engine("test-project")
    assert fake_ee == [{"credentials": "persistent", "project": "test-project"}]


def test_initialize_failure_is_config_error_and_is_retried(monkeypatch, fake_ee):
    def fail(**kwargs):
        raise ee.EEException("Please authorize access to your Earth Engine account")

    monkeypatch.setattr(ee, "Initialize", fail)
    with pytest.raises(ConfigError, match="earthengine authenticate"):
        initialize_earth_engine("test-project")
    assert openlandmap._initialized_projects == set()  # next request tries again


def test_unreadable_service_account_key_never_echoes_the_file(tmp_path, fake_ee):
    key_file = tmp_path / "key.json"
    key_file.write_text(json.dumps({"private_key": "SECRET-KEY-MATERIAL"}), encoding="utf-8")
    with pytest.raises(ConfigError, match="GEE_SERVICE_ACCOUNT_KEY_FILE") as exc:
        initialize_earth_engine("test-project", key_file)
    assert "SECRET" not in exc.value.message
    assert fake_ee == []


def test_missing_service_account_key_file_is_config_error(tmp_path, fake_ee):
    with pytest.raises(ConfigError, match="FileNotFoundError"):
        initialize_earth_engine("test-project", tmp_path / "missing.json")


# ---------------------------------------------------------------- mock + wiring
def test_mock_soil_profile_is_deterministic_and_consistent():
    a = MockSoilProfile().soil_profile(10, -84)
    assert a == MockSoilProfile().soil_profile(10, -84)
    assert [layer.depth_cm for layer in a.layers] == [0, 10, 30]
    for layer in a.layers:
        assert layer.silt_pct == pytest.approx(100 - layer.clay_pct - layer.sand_pct)
        assert layer.texture_class in USDA_TEXTURE_CLASSES.values()
        assert 4.5 < layer.ph < 7.5


def test_build_sources_mock_mode_uses_mock_soil_profile(config, env):
    assert isinstance(build_sources(config, env).soil_profile, MockSoilProfile)


def test_build_sources_live_mode_uses_earth_engine_soil(config, env):
    live_env = env.model_copy(update={"gee_project_id": "test-project"})
    sources = build_sources(config.model_copy(update={"data_mode": DataMode.LIVE}), live_env)
    assert isinstance(sources.soil_profile, EarthEngineSoil)
    assert sources.soil_profile.project_id == "test-project"
    assert set(sources.names()) == {"climate", "soil", "crops"}  # API contract unchanged


def test_earth_engine_project_defaults_to_the_team_project():
    assert EnvSettings(_env_file=None).gee_project_id == DEFAULT_GEE_PROJECT_ID


def test_blank_earth_engine_settings_fall_back_to_defaults():
    env = EnvSettings(_env_file=None, gee_project_id=" ", gee_service_account_key_file="")
    assert env.gee_project_id == DEFAULT_GEE_PROJECT_ID
    assert env.gee_service_account_key_file is None


def test_soil_adapters_implement_protocol(tmp_path):
    assert isinstance(MockSoilProfile(), SoilProfileSource)
    assert isinstance(soil_source(tmp_path), SoilProfileSource)


@pytest.mark.network
def test_live_earth_engine_san_jose(tmp_path):
    source = EarthEngineSoil(
        JsonCache(tmp_path, DataMode.LIVE), project_id=get_env().gee_project_id
    )
    top = source.soil_profile(*SAN_JOSE).layers[0]
    assert top.texture_class is not None
    assert 3 < top.ph < 9
