"""Service-level tests for erosion_risk and get_soil_data, with fake or fixture-backed sources."""

import math
from datetime import date

import pandas as pd
import pytest

from app.cache import JsonCache
from app.domain.models import (
    CropProfile,
    MonthlyClimate,
    Range,
    Season,
    SoilConditions,
    TerrainSample,
    Weights,
)
from app.domain.ranking import rank_rotations
from app.errors import OutOfRegionError, SourceDataError
from app.integrations.mock import MockClimate, MockSoilProfile, MockTerrain
from app.integrations.openlandmap import EarthEngineSoil
from app.services import PLACEHOLDER_RULES_GAP, _data_gaps, erosion_risk, get_soil_data
from app.settings import DataMode
from tests.conftest import load_fixture

JAN = {"lat": 9.93, "lon": -84.08, "start": date(2026, 1, 1), "end": date(2026, 1, 10)}
EXPECTED_KEYS = {
    "elevation_m",
    "slope_pct",
    "terrain_erosion_risk",
    "total_rainfall_mm",
    "avg_daily_rainfall_mm",
    "heavy_rain_days",
    "max_daily_rainfall_mm",
    "combined_erosion_risk",
}


class FakeTerrain:
    name = "fake_terrain"

    def __init__(self, rise_m):
        self.rise_m = rise_m  # east minus west, over 2 x 50 m

    def terrain_sample(self, lat, lon):
        return TerrainSample(
            elevation_m=1605.6,
            north_m=1600.0,
            south_m=1600.0,
            east_m=1600.0 + self.rise_m / 2,
            west_m=1600.0 - self.rise_m / 2,
            spacing_ns_m=50.0,
            spacing_ew_m=50.0,
        )


class FakeWeather:
    name = "fake_weather"

    def __init__(self, rain_mm):
        self.rain_mm = rain_mm

    def daily_weather(self, *, lat, lon, start, end):
        days = pd.date_range(start, periods=len(self.rain_mm), freq="D")
        return pd.DataFrame({"date": days, "temperature_c": 22.0, "rainfall_mm": self.rain_mm})


def run(rise_m, rain_mm):
    return erosion_risk(
        terrain_source=FakeTerrain(rise_m), weather_source=FakeWeather(rain_mm), **JAN
    )


def test_erosion_risk_returns_the_expected_fields_rounded():
    out = run(12.5, [40.0, 85.0, math.nan] + [1.0] * 7)
    assert set(out) == EXPECTED_KEYS
    assert out["elevation_m"] == 1606
    assert out["slope_pct"] == 12.5  # medium terrain
    assert out["terrain_erosion_risk"] == 1
    assert out["total_rainfall_mm"] == 132.0  # the NaN day is skipped
    assert out["avg_daily_rainfall_mm"] == pytest.approx(14.67)  # 132 mm / 9 valid days
    assert out["heavy_rain_days"] == 2
    assert out["max_daily_rainfall_mm"] == 85.0
    assert out["combined_erosion_risk"] == 2  # medium slope + high rain


def test_erosion_risk_flat_dry_land_is_low():
    out = run(0.0, [0.5] * 10)
    assert out["terrain_erosion_risk"] == 0
    assert out["combined_erosion_risk"] == 0


def test_erosion_risk_without_rainfall_data_is_source_error():
    with pytest.raises(SourceDataError, match="no daily rainfall") as exc:
        run(12.5, [math.nan] * 10)
    assert exc.value.details == {"source": "fake_weather"}


def test_erosion_risk_works_offline_with_mock_sources():
    out = erosion_risk(terrain_source=MockTerrain(), weather_source=MockClimate(), **JAN)
    assert set(out) == EXPECTED_KEYS
    assert out["combined_erosion_risk"] >= out["terrain_erosion_risk"]


def test_data_gaps_are_never_empty_with_real_sources_and_verified_crops():
    """Real climate and soil, verified crops, no generic variables: placeholder rules stay a gap."""
    beans = CropProfile(
        id="beans",
        name="Beans",
        scientific_name="x",
        family="Fabaceae",
        is_legume=True,
        cycle_days=90,
        temperature_c=Range(10, 18, 32, 40),
        rainfall_mm=Range(200, 400, 1200, 2000),
        soil_ph=Range(4.5, 5.5, 7.0, 8.5),
        root_depth_m=1.0,
        is_cover_crop=False,
        forage_value=0.5,
        nutrition_density=0.5,
        mycorrhizal_affinity=0.5,
        nitrogen_demand=0.5,
        market_note="",
        sources=("test",),
        verified=True,
    )
    (r,) = rank_rotations(
        crops=[beans],
        seasons=[Season("a", (5, 6, 7)), Season("b", (9, 10, 11))],
        climate=MonthlyClimate(
            temperature_c=(25.0,) * 12,
            rainfall_mm=(200.0,) * 12,
            temperature_max_c=(30.0,) * 12,
            temperature_min_c=(20.0,) * 12,
        ),
        soil=SoilConditions(ph=6.0, moisture_m3m3=0.3),
        weights=Weights(1, 1, 1),
        variables=["temperature", "rainfall", "soil_ph"],
        top_n=1,
    )
    gaps = _data_gaps(r, {"climate": "nasa_power", "soil": "soilgrids"}, ["temperature"])
    assert gaps == [PLACEHOLDER_RULES_GAP]


# ---------------------------------------------------------------- get_soil_data
SOIL_PROPERTIES = {
    "ph",
    "organic_carbon_g_kg",
    "clay_pct",
    "sand_pct",
    "silt_pct",
    "bulk_density_kg_m3",
    "field_capacity_m3m3",
    "texture_class",
}


def fixture_soil_source(tmp_path, fixture="soil_san_jose.json"):
    """The real adapter answering from a saved Earth Engine response (no network)."""
    raw = load_fixture(f"openlandmap/{fixture}")
    return EarthEngineSoil(
        JsonCache(tmp_path, DataMode.LIVE), project_id="test", sampler=lambda lat, lon: raw
    )


def test_get_soil_data_shape_units_and_attribution(tmp_path):
    out = get_soil_data(latitude=9.93, longitude=-84.08, soil_source=fixture_soil_source(tmp_path))
    assert (out["latitude"], out["longitude"]) == (9.93, -84.08)
    assert out["source"] == "OpenLandMap"
    assert "CC-BY-SA" in out["attribution"]
    assert out["resolution_m"] == 250
    assert out["depths_cm"] == [0, 10, 30]
    assert set(out["soil"]) == {"0cm", "10cm", "30cm"}
    assert set(out["units"]) == SOIL_PROPERTIES
    for layer in out["soil"].values():
        assert set(layer) == SOIL_PROPERTIES


def test_get_soil_data_real_values_san_jose(tmp_path):
    out = get_soil_data(latitude=9.93, longitude=-84.08, soil_source=fixture_soil_source(tmp_path))
    assert out["soil"]["0cm"] == {
        "ph": 6.6,
        "organic_carbon_g_kg": 10.0,
        "clay_pct": 38.0,
        "sand_pct": 34.0,
        "silt_pct": 28.0,
        "bulk_density_kg_m3": 1270.0,
        "field_capacity_m3m3": 0.34,
        "texture_class": "clay loam",
    }


def test_get_soil_data_masked_pixel_returns_nulls(tmp_path):
    source = fixture_soil_source(tmp_path, "soil_pacific_ocean.json")
    out = get_soil_data(latitude=9.5, longitude=-86.0, soil_source=source)
    assert all(v is None for layer in out["soil"].values() for v in layer.values())


@pytest.mark.parametrize(("lat", "lon"), [(91, 0), (-90.5, 0), (0, 180.1), (math.nan, 0)])
def test_get_soil_data_rejects_impossible_coordinates(lat, lon):
    with pytest.raises(OutOfRegionError, match="not a valid coordinate") as exc:
        get_soil_data(latitude=lat, longitude=lon, soil_source=MockSoilProfile())
    assert exc.value.details["bbox"] == [-180.0, -90.0, 180.0, 90.0]


def test_get_soil_data_works_offline_with_mock_source():
    out = get_soil_data(latitude=9.93, longitude=-84.08, soil_source=MockSoilProfile())
    assert out["source"] == "mock"
    assert out["soil"]["0cm"]["texture_class"] is not None
