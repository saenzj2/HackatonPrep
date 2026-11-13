"""Interfaces every data source implements. Swap a source without touching domain or api.

Adapters MUST return domain models in normalized units (°C, mm, pH, m³/m³), never raw payloads,
and raise only SourceUnavailableError / SourceDataError / ConfigError (see docs/errors.md).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.models import CropProfile, MonthlyClimate, SoilConditions


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
