"""Deterministic fake data shaped like Costa Rica: same lat/lon → same values, no network.

Lets the frontend build against real-looking responses before any real source is wired up.
"""

from __future__ import annotations

import calendar
import math
import random
from datetime import date
from typing import Literal

import pandas as pd

from app.domain.enso import SEASONS, EnsoIndex, EnsoSeason
from app.domain.models import MonthlyClimate, SoilConditions, SoilLayer, SoilProfile, TerrainSample
from app.domain.soil import silt_pct

# Relative monthly rainfall for a Pacific-slope Costa Rica regime:
# dry Dec–Apr, rains from May, short "veranillo" in Jul, peak Sep–Oct.
_RAIN_SHAPE = (0.15, 0.10, 0.15, 0.45, 1.25, 1.20, 0.95, 1.10, 1.50, 1.65, 1.05, 0.40)
_TEMP_SHAPE = (-0.6, 0.0, 0.9, 1.2, 0.5, 0.0, -0.1, -0.1, -0.3, -0.5, -0.6, -0.7)
# Half the daily range (°C), wider in the dry season. Alajuela POWER normals: ~15 → ~13 °C.
_HALF_DAILY_RANGE = (7.5, 8.0, 8.5, 8.5, 8.0, 7.0, 7.0, 7.0, 6.5, 6.5, 6.5, 7.0)
_WET_DAY_PROBABILITY = 0.6  # share of days with rain; the monthly total is spread over them
_MOCK_SPACING_M = 30.0  # about one SRTM sample
# Mock soil profiles: (USDA texture class, clay %, sand %) near the middle of each class, so a
# jitter of ±3 points keeps the fractions consistent with the class name.
_MOCK_TEXTURES = (("clay loam", 33.0, 32.0), ("loam", 20.0, 40.0), ("clay", 50.0, 20.0))
_MOCK_DEPTHS_CM = (0, 10, 30)


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

    def daily_history(self, *, lat: float, lon: float, start: date, end: date) -> pd.DataFrame:
        """Fake long daily history, same columns as NASA POWER daily_history. Wet days follow
        the monthly rain shape, so dry-season sowings meet dry spells, as in the real data."""
        monthly = self.monthly_climate(lat, lon)
        rng = _rng(f"history:{start}:{end}", lat, lon)
        days = pd.date_range(start, end, freq="D")
        rain, tmax, tmin, wetness = [], [], [], []
        for day in days:
            m = day.month - 1
            wet_share = min(0.9, _WET_DAY_PROBABILITY * _RAIN_SHAPE[m])
            month_days = calendar.monthrange(day.year, day.month)[1]
            wet_day_mean_mm = monthly.rainfall_mm[m] / (month_days * max(wet_share, 0.05))
            is_wet = rng.random() < wet_share
            rain.append(round(rng.expovariate(1 / wet_day_mean_mm), 2) if is_wet else 0.0)
            tmax.append(round(monthly.temperature_max_c[m] + rng.gauss(0, 1.0), 2))
            tmin.append(round(monthly.temperature_min_c[m] + rng.gauss(0, 0.8), 2))
            wetness.append(round(min(1.0, 0.45 + 0.25 * _RAIN_SHAPE[m] + rng.gauss(0, 0.03)), 3))
        return pd.DataFrame(
            {
                "date": days,
                "rainfall_mm": rain,
                "rainfall_merra2_mm": [round(r * 0.7, 2) for r in rain],
                "temperature_max_c": tmax,
                "temperature_min_c": tmin,
                "root_wetness": wetness,
            }
        )


class MockSoil:
    name = "mock"

    def soil(self, lat: float, lon: float) -> SoilConditions:
        rng = _rng("soil", lat, lon)
        base = rng.uniform(0.18, 0.38)
        # Moisture follows the rains about a month later, like SMAP in Costa Rica.
        peak = max(_RAIN_SHAPE)
        monthly = tuple(round(base * (0.7 + 0.3 * _RAIN_SHAPE[m - 1] / peak), 3) for m in range(12))
        return SoilConditions(
            ph=round(rng.uniform(5.0, 6.8), 2),
            moisture_m3m3=round(sum(monthly) / len(monthly), 3),
            moisture_monthly_m3m3=monthly,
            wetness_monthly=tuple(round(min(1.0, m / 0.45), 3) for m in monthly),
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


class MockSoilProfile:
    name = "mock"
    attribution = "Deterministic mock data, not real measurements"
    resolution_m = 250  # same shape as the real source (OpenLandMap)

    def soil_profile(self, lat: float, lon: float) -> SoilProfile:
        """Fake 0/10/30 cm profile: carbon falls and density rises with depth, like real soils."""
        rng = _rng("soil_profile", lat, lon)
        texture, clay_base, sand_base = rng.choice(_MOCK_TEXTURES)
        ph = rng.uniform(5.0, 6.8)
        carbon_g_kg = rng.uniform(15.0, 45.0)
        layers = []
        for i, depth in enumerate(_MOCK_DEPTHS_CM):
            clay = round(clay_base + rng.uniform(-3, 3))
            sand = round(sand_base + rng.uniform(-3, 3))
            layers.append(
                SoilLayer(
                    depth_cm=depth,
                    ph=round(ph + 0.1 * i, 1),
                    organic_carbon_g_kg=float(round(carbon_g_kg * (1 - 0.25 * i) / 5) * 5),
                    clay_pct=float(clay),
                    sand_pct=float(sand),
                    silt_pct=silt_pct(clay, sand),
                    bulk_density_kg_m3=float(round(rng.uniform(1100, 1300) + 40 * i, -1)),
                    field_capacity_m3m3=round(rng.uniform(0.28, 0.40), 2),
                    texture_class=texture,
                )
            )
        return SoilProfile(lat=lat, lon=lon, layers=tuple(layers))


class MockEnso:
    """Deterministic fake El Niño index: a ~4-year cycle, RONI slightly below ONI like the real
    ones in recent decades. Ends with ASO 2026 so `enso_now` has a value."""

    name = "mock"

    def index(self, name: Literal["RONI", "ONI"]) -> EnsoIndex:
        offset = 0.0 if name == "RONI" else 0.3
        seasons = []
        for year in range(1950, 2027):
            for i, season in enumerate(SEASONS):
                if year == 2026 and i > SEASONS.index("ASO"):
                    break
                t = (year - 1950) * 12 + i
                anomaly = 1.3 * math.sin(2 * math.pi * t / 47) + offset
                seasons.append(EnsoSeason(season=season, year=year, anomaly_c=round(anomaly, 2)))
        return EnsoIndex(name=name, seasons=tuple(seasons))
