"""Deterministic fake data shaped like Costa Rica: same lat/lon → same values, no network.

Lets the frontend build against real-looking responses before any real source is wired up.
"""

from __future__ import annotations

import random

from app.domain.models import MonthlyClimate, SoilConditions

# Relative monthly rainfall for a Pacific-slope Costa Rica regime:
# dry Dec–Apr, rains from May, short "veranillo" in Jul, peak Sep–Oct.
_RAIN_SHAPE = (0.15, 0.10, 0.15, 0.45, 1.25, 1.20, 0.95, 1.10, 1.50, 1.65, 1.05, 0.40)
_TEMP_SHAPE = (-0.6, 0.0, 0.9, 1.2, 0.5, 0.0, -0.1, -0.1, -0.3, -0.5, -0.6, -0.7)


def _rng(kind: str, lat: float, lon: float) -> random.Random:
    return random.Random(f"{kind}:{lat:.2f}:{lon:.2f}")


class MockClimate:
    name = "mock"

    def monthly_climate(self, lat: float, lon: float) -> MonthlyClimate:
        rng = _rng("climate", lat, lon)
        base_temp = rng.uniform(20.0, 28.0)
        annual_rain = rng.uniform(1400.0, 3200.0)
        shape_total = sum(_RAIN_SHAPE)
        return MonthlyClimate(
            temperature_c=tuple(round(base_temp + d, 2) for d in _TEMP_SHAPE),
            rainfall_mm=tuple(round(annual_rain * s / shape_total, 1) for s in _RAIN_SHAPE),
        )


class MockSoil:
    name = "mock"

    def soil(self, lat: float, lon: float) -> SoilConditions:
        rng = _rng("soil", lat, lon)
        return SoilConditions(
            ph=round(rng.uniform(5.0, 6.8), 2),
            moisture_m3m3=round(rng.uniform(0.18, 0.38), 3),
        )
