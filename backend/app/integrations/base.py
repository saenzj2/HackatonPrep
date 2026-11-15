"""Interfaces every data source implements. Swap a source without touching domain or api.

Adapters MUST return domain models in normalized units (°C, mm, pH, m³/m³), never raw payloads,
and raise only SourceUnavailableError / SourceDataError / ConfigError (see docs/errors.md).
"""

from __future__ import annotations

from datetime import date
from typing import Literal, Protocol, runtime_checkable

import pandas as pd

from app.domain.enso import EnsoIndex
from app.domain.models import (
    CropProfile,
    MonthlyClimate,
    SoilConditions,
    SoilProfile,
    TerrainSample,
)


@runtime_checkable
class ClimateSource(Protocol):
    name: str

    def monthly_climate(self, lat: float, lon: float) -> MonthlyClimate: ...


@runtime_checkable
class SoilSource(Protocol):
    name: str

    def soil(self, lat: float, lon: float) -> SoilConditions: ...


@runtime_checkable
class CropSource(Protocol):
    name: str

    def all(self) -> dict[str, CropProfile]: ...


@runtime_checkable
class DailyWeatherSource(Protocol):
    """Daily series: DataFrame with date, temperature_c, rainfall_mm (mm/day); NaN = missing day."""

    name: str

    def daily_weather(self, *, lat: float, lon: float, start: date, end: date) -> pd.DataFrame: ...


@runtime_checkable
class DailyHistorySource(Protocol):
    """Long daily history for POST /plan-risk: DataFrame with date, rainfall_mm (IMERG),
    rainfall_merra2_mm, temperature_max_c, temperature_min_c (°C), root_wetness (0..1).
    NaN = missing value (see nasa_power.parse_daily_history)."""

    name: str

    def daily_history(self, *, lat: float, lon: float, start: date, end: date) -> pd.DataFrame: ...


@runtime_checkable
class EnsoIndexSource(Protocol):
    """NOAA CPC El Niño index by name ("RONI" official, "ONI" legacy), 1950 → latest season."""

    name: str

    def index(self, name: Literal["RONI", "ONI"]) -> EnsoIndex: ...


@runtime_checkable
class TerrainSource(Protocol):
    name: str

    def terrain_sample(self, lat: float, lon: float) -> TerrainSample: ...


@runtime_checkable
class SoilProfileSource(Protocol):
    """Soil properties by depth (pH, carbon, texture, density, field capacity); None = no data."""

    name: str
    attribution: str  # credit line to show with the data (license terms)
    resolution_m: int  # nominal pixel size of the maps

    def soil_profile(self, lat: float, lon: float) -> SoilProfile: ...
