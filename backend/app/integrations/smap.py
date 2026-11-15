"""NASA SMAP L4 root-zone soil moisture (0-100 cm, m³/m³), monthly means, via Google Earth Engine.

Same 3-part pattern as nasa_power.py and openlandmap.py:
  1. `fetch_raw()`              one Earth Engine request: 12 monthly means at a point.
  2. `parse_monthly_soil_water()` pure function: validates 12 moisture + 12 wetness values.
  3. `monthly_soil_water()`       goes through JsonCache; the means are historical, so a cached
                                point is reused in every mode (like the OpenLandMap maps).

Dataset: NASA/SMAP/SPL4SMGP/008 (SMAP L4 Global 3-hourly 9 km surface and root zone soil moisture),
bands `sm_rootzone` (m³/m³) and `sm_rootzone_wetness` (relative saturation 0-1, against the model's
own porosity). To keep the request small (the full 3-hourly series hits Earth Engine's memory
limit) it uses one reading per day (13:30 UTC = 07:30 in Costa Rica), YEARS, and the mean of the
pixels within RADIUS_M of the point. Notes: docs/sources/smap.md

Earth Engine setup and error handling are shared with openlandmap.py.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.cache import JsonCache
from app.domain.models import MONTHS, MonthlySoilWater
from app.errors import ConfigError, SourceDataError
from app.integrations.openlandmap import call_earth_engine, initialize_earth_engine

SOURCE = "nasa_smap"
ATTRIBUTION = (
    "NASA SMAP L4 Global 3-hourly 9 km Surface and Root Zone Soil Moisture (SPL4SMGP v008), "
    "Reichle et al., NASA NSIDC DAAC, via Google Earth Engine"
)
ASSET_ID = "NASA/SMAP/SPL4SMGP/008"
MOISTURE_BAND = "sm_rootzone"  # volumetric water content, root zone 0-100 cm, m³/m³
WETNESS_BAND = "sm_rootzone_wetness"  # relative saturation 0 (dry) .. 1 (saturated), same layer
YEARS = (2020, 2024)  # inclusive; five full recent years
HOUR_UTC = 13  # images are at hh:30; 13:30 UTC is one reading per day
RADIUS_M = 15_000  # mean of the ~9 km pixels around the point (one pixel can be masked water)
SCALE_M = 9_000  # native grid ~9 km
VALID_RANGE_M3M3 = (0.0, 0.9)  # band range in the Earth Engine catalog
VALID_RANGE_WETNESS = (0.0, 1.0)
COORD_DECIMALS = 2  # ~1 km, far below the 9 km pixels; same as NASA POWER
MONTH_KEYS = [f"m{m:02d}" for m in range(1, MONTHS + 1)]  # moisture, January first
WETNESS_KEYS = [f"w{m:02d}" for m in range(1, MONTHS + 1)]  # wetness, January first


def sample_monthly(lat: float, lon: float) -> Any:
    """ONE Earth Engine request: mean moisture and wetness per calendar month over YEARS, around
    the point. Returns {"m01".."m12": moisture, "w01".."w12": wetness}, each float or None.
    Earth Engine must be initialized first.
    """
    import ee  # noqa: PLC0415  (only when Earth Engine is actually used)

    area = ee.Geometry.Point([lon, lat]).buffer(RADIUS_M)
    daily = (
        ee.ImageCollection(ASSET_ID)
        .select([MOISTURE_BAND, WETNESS_BAND])
        .filterDate(f"{YEARS[0]}-01-01", f"{YEARS[1] + 1}-01-01")
        .filter(ee.Filter.calendarRange(HOUR_UTC, HOUR_UTC, "hour"))
        .map(lambda img: img.clip(area))  # clipping keeps the request within memory limits
    )
    monthly = ee.Image.cat(
        [
            daily.filter(ee.Filter.calendarRange(m, m, "month")).mean().rename([mk, wk])
            for m, (mk, wk) in enumerate(zip(MONTH_KEYS, WETNESS_KEYS, strict=True), start=1)
        ]
    )
    return monthly.reduceRegion(reducer=ee.Reducer.mean(), geometry=area, scale=SCALE_M).getInfo()


def _monthly_values(
    raw: dict[str, Any], keys: list[str], valid: tuple[float, float], what: str
) -> tuple[float, ...]:
    values = []
    for key in keys:
        value = raw.get(key)
        if value is None:
            raise SourceDataError(
                f"SMAP has no {what} for this location ({key} is empty; water or no land "
                "pixels nearby)",
                details={"source": SOURCE, "month": key},
            )
        if (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(value)
        ):
            raise SourceDataError(
                f"Unexpected SMAP value for {key}: {value!r}, expected a number",
                details={"source": SOURCE, "month": key},
            )
        low, high = valid
        if not low <= value <= high:
            raise SourceDataError(
                f"SMAP {key} is {value}, outside {low}..{high}",
                details={"source": SOURCE, "month": key},
            )
        values.append(round(float(value), 4))
    return tuple(values)


def parse_monthly_soil_water(raw: dict[str, Any]) -> MonthlySoilWater:
    """{"m01": 0.319, ..., "w01": 0.61, ...} → 12 moisture (m³/m³) and 12 wetness (0-1) values,
    January first. Native units are already m³/m³ and a 0-1 fraction.

    A month with no value means the area has no SMAP land pixels (open water, for example):
    that is an error, never a guess.
    """
    return MonthlySoilWater(
        moisture_m3m3=_monthly_values(raw, MONTH_KEYS, VALID_RANGE_M3M3, "soil moisture"),
        wetness=_monthly_values(raw, WETNESS_KEYS, VALID_RANGE_WETNESS, "soil wetness"),
    )


class SmapSoilMoisture:
    name = SOURCE
    attribution = ATTRIBUTION
    resolution_m = SCALE_M

    def __init__(
        self,
        cache: JsonCache,
        *,
        project_id: str | None,
        service_account_key_file: Path | None = None,
        sampler: Callable[[float, float], Any] | None = None,
    ) -> None:
        """`sampler` replaces the real Earth Engine call (tests pass a fake). Without it, Earth
        Engine is initialized on the first uncached request."""
        self.cache = cache
        self.project_id = project_id
        self.service_account_key_file = service_account_key_file
        self.sampler = sampler

    @staticmethod
    def point_params(lat: float, lon: float) -> dict[str, Any]:
        # Also the cache key: a different asset, period or method never reuses old entries.
        return {
            "asset": ASSET_ID,
            "bands": [MOISTURE_BAND, WETNESS_BAND],
            "years": list(YEARS),
            "hour_utc": HOUR_UTC,
            "radius_m": RADIUS_M,
            "latitude": round(lat, COORD_DECIMALS),
            "longitude": round(lon, COORD_DECIMALS),
        }

    def _default_sampler(self) -> Callable[[float, float], Any]:
        if self.project_id is None:
            raise ConfigError(
                "No Earth Engine project configured (GEE_PROJECT_ID); it is needed to fetch new "
                "SMAP soil moisture (data_mode=live)",
                details={"source": SOURCE},
            )
        initialize_earth_engine(self.project_id, self.service_account_key_file)
        return sample_monthly

    def fetch_raw(self, params: dict[str, Any]) -> dict[str, Any]:
        sampler = self.sampler or self._default_sampler()
        return call_earth_engine(
            lambda: sampler(params["latitude"], params["longitude"]), source=SOURCE
        )

    def _fetch_valid(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate before the cache stores it, so a bad answer is never cached."""
        raw = self.fetch_raw(params)
        parse_monthly_soil_water(raw)
        return raw

    def monthly_soil_water(self, lat: float, lon: float) -> MonthlySoilWater:
        """Mean root-zone moisture (m³/m³) and wetness (0-1) per calendar month, January first."""
        params = self.point_params(lat, lon)
        # Historical means don't change: reuse a cached point in every mode, like OpenLandMap.
        raw = self.cache.peek(SOURCE, params)
        if raw is None:
            raw = self.cache.get_or_fetch(SOURCE, params, lambda: self._fetch_valid(params))
        return parse_monthly_soil_water(raw)
