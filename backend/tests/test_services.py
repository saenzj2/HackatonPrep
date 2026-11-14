"""Service-level tests for erosion_risk, with in-memory fake sources (no HTTP, no cache)."""

import math
from datetime import date

import pandas as pd
import pytest

from app.domain.models import TerrainSample
from app.errors import SourceDataError
from app.services import erosion_risk

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
