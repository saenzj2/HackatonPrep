"""Source registry: picks the adapter for each data type based on data_mode.

To add a source: implement the protocol from base.py in a new module, then wire it here.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.cache import JsonCache
from app.integrations.base import (
    ClimateSource,
    CropSource,
    DailyHistorySource,
    DailyWeatherSource,
    EnsoIndexSource,
    PerennialCropSource,
    SoilProfileSource,
    SoilSource,
    TerrainSource,
)
from app.integrations.ecocrop import EcoCropCatalog, PerennialCropCatalog
from app.integrations.measured_soil import MeasuredSoil
from app.integrations.mock import MockClimate, MockEnso, MockSoil, MockSoilProfile, MockTerrain
from app.integrations.nasa_power import NasaPowerClimate
from app.integrations.noaa_enso import NoaaEnso
from app.integrations.openlandmap import EarthEngineSoil
from app.integrations.opentopography import OpenTopographyElevation
from app.integrations.smap import SmapSoilMoisture
from app.settings import DataMode, EnvSettings, MvpConfig


@dataclass(frozen=True)
class Sources:
    climate: ClimateSource
    soil: SoilSource
    crops: CropSource
    daily: DailyWeatherSource  # GET /weather/daily, GET /erosion (rain)
    terrain: TerrainSource
    soil_profile: SoilProfileSource  # GET /soil (services.get_soil_data)
    history: DailyHistorySource  # POST /plan-risk: ~25 years of daily IMERG rain + MERRA-2
    enso: EnsoIndexSource  # POST /plan-risk: NOAA CPC RONI (official) and ONI (legacy)
    perennials: PerennialCropSource  # GET /permanent-crops: cacao, coffee… (local CSV)

    def names(self) -> dict[str, str]:
        # Only the sources the current API reports (DataSources in the contract).
        return {"climate": self.climate.name, "soil": self.soil.name, "crops": self.crops.name}


def build_sources(config: MvpConfig, env: EnvSettings) -> Sources:
    crops = EcoCropCatalog(env.crop_catalog)
    perennials = PerennialCropCatalog(env.perennial_crop_catalog)
    if config.data_mode == DataMode.MOCK:
        climate = MockClimate()
        return Sources(
            climate=climate,
            soil=MockSoil(),
            crops=crops,
            daily=climate,
            terrain=MockTerrain(),
            soil_profile=MockSoilProfile(),
            history=climate,
            enso=MockEnso(),
            perennials=perennials,
        )
    cache = JsonCache(env.cache_dir, config.data_mode, snapshot=env.cache_snapshot_dir)
    power = NasaPowerClimate(cache)
    # Earth Engine starts on the first uncached request, never here (no network at startup).
    project, key_file = env.gee_project_id, env.gee_service_account_key_file
    soil_profile = EarthEngineSoil(cache, project_id=project, service_account_key_file=key_file)
    moisture = SmapSoilMoisture(cache, project_id=project, service_account_key_file=key_file)
    return Sources(
        climate=power,
        # Real soil for scoring: OpenLandMap pH + NASA SMAP monthly moisture (both cached).
        soil=MeasuredSoil(profile=soil_profile, moisture=moisture),
        crops=crops,
        daily=power,
        # No key needed until a location isn't cached yet (then ConfigError names the variable).
        terrain=OpenTopographyElevation(cache, env.open_topography_key),
        soil_profile=soil_profile,
        history=power,
        enso=NoaaEnso(cache),
        perennials=perennials,
    )
