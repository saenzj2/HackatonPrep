"""Real soil for scoring: pH from OpenLandMap and monthly root-zone moisture from NASA SMAP.

Implements SoilSource (what suitability scoring uses) on top of two existing adapters, so there is
no new network code here:
  - pH: mean of the OpenLandMap layers at 0, 10 and 30 cm (the main root zone). Layers without a
    value are skipped; no value at any depth is an error, never a guess.
  - moisture and wetness: the 12 SMAP monthly means; `moisture_m3m3` is the yearly mean.
Both are cached by their adapters, so cached mode needs no network.
"""

from __future__ import annotations

from statistics import mean

from app.domain.models import SoilConditions
from app.errors import SourceDataError
from app.integrations.base import SoilProfileSource
from app.integrations.smap import SmapSoilMoisture

SOURCE = "openlandmap+nasa_smap"


class MeasuredSoil:
    name = SOURCE

    def __init__(self, *, profile: SoilProfileSource, moisture: SmapSoilMoisture) -> None:
        self.profile = profile
        self.moisture = moisture

    def soil(self, lat: float, lon: float) -> SoilConditions:
        layers = self.profile.soil_profile(lat, lon).layers
        phs = [layer.ph for layer in layers if layer.ph is not None]
        if not phs:
            raise SourceDataError(
                "OpenLandMap has no soil pH for this location (water or no prediction)",
                details={"source": "openlandmap"},
            )
        water = self.moisture.monthly_soil_water(lat, lon)
        return SoilConditions(
            ph=round(mean(phs), 2),
            moisture_m3m3=round(mean(water.moisture_m3m3), 4),
            moisture_monthly_m3m3=water.moisture_m3m3,
            wetness_monthly=water.wetness,
            # Shallowest layer with a texture class; it only words the waterlogging warning.
            texture_class=next((x.texture_class for x in layers if x.texture_class), None),
        )
