"""Source registry: picks the adapter for each data type based on data_mode.

To add a source: implement the protocol from base.py in a new module, then wire it here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.cache import JsonCache
from app.integrations.base import ClimateSource, CropSource, SoilSource
from app.integrations.ecocrop import EcoCropCatalog
from app.integrations.mock import MockClimate, MockSoil
from app.integrations.nasa_power import NasaPowerClimate
from app.settings import DataMode, EnvSettings, MvpConfig


@dataclass(frozen=True)
class Sources:
    climate: ClimateSource
    soil: SoilSource
    crops: CropSource

    def names(self) -> dict[str, str]:
        return {"climate": self.climate.name, "soil": self.soil.name, "crops": self.crops.name}


def build_sources(config: MvpConfig, env: EnvSettings) -> Sources:
    crops = EcoCropCatalog(env.crop_catalog)
    if config.data_mode == DataMode.MOCK:
        return Sources(climate=MockClimate(), soil=MockSoil(), crops=crops)
    cache = JsonCache(env.cache_dir, config.data_mode)
    return Sources(
        climate=NasaPowerClimate(cache),
        soil=MockSoil(),  # TODO: real soil source (SMAP moisture, SoilGrids pH). See decisions.md
        crops=crops,
    )
