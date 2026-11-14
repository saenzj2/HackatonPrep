"""Deterministic fake data shaped like Costa Rica: same lat/lon → same values, no network.

Lets the frontend build against real-looking responses before any real source is wired up.
"""

from __future__ import annotations

import calendar
import random
from datetime import date

import pandas as pd

from app.domain.models import MonthlyClimate, SoilConditions, TerrainSample

# Relative monthly rainfall for a Pacific-slope Costa Rica regime:
# dry Dec–Apr, rains from May, short "veranillo" in Jul, peak Sep–Oct.
_RAIN_SHAPE = (0.15, 0.10, 0.15, 0.45, 1.25, 1.20, 0.95, 1.10, 1.50, 1.65, 1.05, 0.40)
_TEMP_SHAPE = (-0.6, 0.0, 0.9, 1.2, 0.5, 0.0, -0.1, -0.1, -0.3, -0.5, -0.6, -0.7)
# Half the daily range (°C), wider in the dry season. Alajuela POWER normals: ~15 → ~13 °C.
_HALF_DAILY_RANGE = (7.5, 8.0, 8.5, 8.5, 8.0, 7.0, 7.0, 7.0, 6.5, 6.5, 6.5, 7.0)
_WET_DAY_PROBABILITY = 0.6  # share of days with rain; the monthly total is spread over them
_MOCK_SPACING_M = 30.0  # about one SRTM sample


def _rng(kind: str, lat: float, lon: float) -> random.Random:
    return random.Random(f"{kind}:{lat:.2f}:{lon:.2f}")


class MockClimate:
    name = "mock"

    def monthly_climate(self, lat: float, lon: float) -> MonthlyClimate:
        rng = _rng("climate", lat, lon)
        base_temp = rng.uniform(20.0, 28.0)
        annual_rain = rng.uniform(1400.0, 3200.0)
        shape_total = sum(_RAIN_SHAPE)
        temps = [base_temp + d for d in _TEMP_SHAPE]
        return MonthlyClimate(
            temperature_c=tuple(round(t, 2) for t in temps),
            rainfall_mm=tuple(round(annual_rain * s / shape_total, 1) for s in _RAIN_SHAPE),
            temperature_max_c=tuple(
                round(t + h, 2) for t, h in zip(temps, _HALF_DAILY_RANGE, strict=True)
            ),
            temperature_min_c=tuple(
                round(t - h, 2) for t, h in zip(temps, _HALF_DAILY_RANGE, strict=True)
            ),
        )

    def daily_weather(self, *, lat: float, lon: float, start: date, end: date) -> pd.DataFrame:
        """Fake daily series consistent with monthly_climate(): same columns as NASA POWER daily."""
        monthly = self.monthly_climate(lat, lon)
        rng = _rng(f"daily:{start}:{end}", lat, lon)
        days = pd.date_range(start, end, freq="D")
        temperature_c, rainfall_mm = [], []
        for day in days:
            m = day.month - 1
            wet_day_mean_mm = monthly.rainfall_mm[m] / (
                calendar.monthrange(day.year, day.month)[1] * _WET_DAY_PROBABILITY
            )
            is_wet = rng.random() < _WET_DAY_PROBABILITY
            rainfall_mm.append(round(rng.expovariate(1 / wet_day_mean_mm), 2) if is_wet else 0.0)
            temperature_c.append(round(monthly.temperature_c[m] + rng.gauss(0, 0.8), 2))
        return pd.DataFrame(
            {"date": days, "temperature_c": temperature_c, "rainfall_mm": rainfall_mm}
        )


class MockSoil:
    name = "mock"

    def soil(self, lat: float, lon: float) -> SoilConditions:
        rng = _rng("soil", lat, lon)
        return SoilConditions(
            ph=round(rng.uniform(5.0, 6.8), 2),
            moisture_m3m3=round(rng.uniform(0.18, 0.38), 3),
        )


class MockTerrain:
    name = "mock"

    def terrain_sample(self, lat: float, lon: float) -> TerrainSample:
        """Fake 5-point elevation sample: slope 0 to 25 %, all of it on the east-west axis."""
        rng = _rng("terrain", lat, lon)
        elevation_m = round(rng.uniform(50.0, 2500.0), 1)
        half_rise_m = rng.uniform(0.0, 0.25) * _MOCK_SPACING_M  # slope fraction x spacing
        return TerrainSample(
            elevation_m=elevation_m,
            north_m=elevation_m,
            south_m=elevation_m,
            east_m=round(elevation_m + half_rise_m, 2),
            west_m=round(elevation_m - half_rise_m, 2),
            spacing_ns_m=_MOCK_SPACING_M,
            spacing_ew_m=_MOCK_SPACING_M,
        )
