"""Source registry: picks the adapter for each data type based on data_mode.

To add a source: implement the protocol from base.py in a new module, then wire it here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.cache import JsonCache
from app.integrations.base import (
    ClimateSource,
    CropSource,
    DailyWeatherSource,
    SoilSource,
    TerrainSource,
)
from app.integrations.ecocrop import EcoCropCatalog
from app.integrations.mock import MockClimate, MockSoil, MockTerrain
from app.integrations.nasa_power import NasaPowerClimate
from app.integrations.opentopography import OpenTopographyElevation
from app.settings import DataMode, EnvSettings, MvpConfig


@dataclass(frozen=True)
class Sources:
    climate: ClimateSource
    soil: SoilSource
    crops: CropSource
    daily: DailyWeatherSource  # erosion risk (services.erosion_risk); no endpoint yet
    terrain: TerrainSource

    def names(self) -> dict[str, str]:
        # Only the sources the current API reports (DataSources in the contract).
        return {"climate": self.climate.name, "soil": self.soil.name, "crops": self.crops.name}


def build_sources(config: MvpConfig, env: EnvSettings) -> Sources:
    crops = EcoCropCatalog(env.crop_catalog)
    if config.data_mode == DataMode.MOCK:
        climate = MockClimate()
        return Sources(
            climate=climate, soil=MockSoil(), crops=crops, daily=climate, terrain=MockTerrain()
        )
    cache = JsonCache(env.cache_dir, config.data_mode)
    power = NasaPowerClimate(cache)
    return Sources(
        climate=power,
        soil=MockSoil(),  # TODO: real soil source (SMAP moisture, SoilGrids pH). See decisions.md
        crops=crops,
        daily=power,
        # No key needed until a location isn't cached yet (then ConfigError names the variable).
        terrain=OpenTopographyElevation(cache, env.open_topography_key),
    )
