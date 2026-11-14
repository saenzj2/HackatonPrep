"""OpenTopography point elevation adapter (SRTM GL1, ~30 m): elevation and slope samples.

Same 3-part pattern as nasa_power.py:
  1. `fetch_raw()`        one HTTP call to /v1/elevation (one point per call) and nothing else.
  2. `parse_elevation()`  pure function, raw JSON → metres, rejects voids and failed answers.
  3. `elevation_m()` / `terrain_sample()` go through JsonCache, one cache entry per point.

API docs: https://portal.opentopography.org/apidocs/#/Public/getPointElevation
Dataset notes: docs/sources/opentopography.md

The API key travels in the query string (`API_Key`), so this module never lets a URL reach an
error message, a traceback or the cache: the key is added only at request time.
"""

from __future__ import annotations

import math
from typing import Any

import httpx
from pydantic import SecretStr

from app.cache import JsonCache
from app.domain.models import TerrainSample
from app.errors import ConfigError, SourceDataError, SourceUnavailableError

SOURCE = "opentopography"
BASE_URL = "https://portal.opentopography.org/API/v1/elevation"
DATASET = "SRTM_GL1"  # SRTM GL1, 1 arc-second (~30 m). Used for every request, never mixed.
ARCSEC_DEG = 1 / 3600  # SRTM GL1 posting: samples sit on a 1 arc-second grid
SRTM_VOID_M = -32768.0  # SRTM "no data" value (radar shadow, water)
EARTH_RADIUS_M = 6_371_008.8  # mean Earth radius; <0.5 % error on 30 m spacings, fine for slope
COORD_DECIMALS = 6  # ~0.1 m: keeps neighbouring samples (30 m apart) in separate cache entries


def parse_elevation(raw: dict[str, Any]) -> float:
    """OpenTopography point JSON → elevation in metres (native unit, no conversion).

    Example input: {"Status": "Success", "Elevation": 1164.0, "Unit": "Meters", ...}
    """
    # A failed lookup still answers HTTP 200 on some errors; trust the Status field, not the code.
    if raw.get("Status") != "Success":
        raise SourceDataError(
            f"OpenTopography could not return an elevation ({raw.get('Message', 'no message')})",
            details={"source": SOURCE},
        )
    try:
        elevation_m = float(raw["Elevation"])
    except (KeyError, TypeError, ValueError) as e:
        raise SourceDataError(
            f"Unexpected OpenTopography payload ({type(e).__name__}: {e})",
            details={"source": SOURCE},
        ) from e
    if raw.get("Unit", "Meters") != "Meters":
        raise SourceDataError(
            f"OpenTopography answered in {raw.get('Unit')}, expected Meters",
            details={"source": SOURCE},
        )
    if elevation_m == SRTM_VOID_M or not math.isfinite(elevation_m):
        raise SourceDataError(
            "OpenTopography has no SRTM elevation for this point (data void)",
            details={"source": SOURCE},
        )
    return elevation_m


def snap_to_srtm_grid(deg: float) -> float:
    """Nearest SRTM sample (whole arc-second), so the centre and its neighbours are exactly one
    sample apart, and nearby clicks reuse the same cached points."""
    return round(round(deg / ARCSEC_DEG) * ARCSEC_DEG, COORD_DECIMALS)


class OpenTopographyElevation:
    name = SOURCE

    def __init__(
        self, cache: JsonCache, api_key: SecretStr | None, client: httpx.Client | None = None
    ) -> None:
        self.cache = cache
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=30.0)

    @staticmethod
    def point_params(lat: float, lon: float) -> dict[str, Any]:
        # Also the cache key, written to disk: it must NEVER contain the API key.
        return {
            "dataset": DATASET,
            "latitude": round(lat, COORD_DECIMALS),
            "longitude": round(lon, COORD_DECIMALS),
        }

    def fetch_raw(self, params: dict[str, Any]) -> dict[str, Any]:
        if self.api_key is None:
            # Only reached when the cache can't answer, so cached mode works without a key.
            raise ConfigError(
                "OPEN_TOPOGRAPHY_KEY is not set in backend/.env; it is needed to fetch new "
                "elevation data (data_mode=live)",
                details={"source": SOURCE},
            )
        query = {**params, "API_Key": self.api_key.get_secret_value()}
        try:
            resp = self.client.get(BASE_URL, params=query)
        except httpx.HTTPError as e:
            # Only the class name: some httpx messages include the request URL (and so the key).
            raise SourceUnavailableError(
                f"OpenTopography request failed ({type(e).__name__})", details={"source": SOURCE}
            ) from e
        # Status checked by hand instead of raise_for_status(): httpx's HTTPStatusError message
        # contains the full URL, key included, and would end up in the logged traceback.
        if resp.is_error:
            raise SourceUnavailableError(
                f"OpenTopography answered HTTP {resp.status_code}",
                details={"source": SOURCE, "status": resp.status_code},
            )
        try:
            data = resp.json()
        except ValueError as e:
            raise SourceDataError(
                "OpenTopography returned a non-JSON body", details={"source": SOURCE}
            ) from e
        if not isinstance(data, dict):
            raise SourceDataError(
                f"OpenTopography returned {type(data).__name__}, expected an object",
                details={"source": SOURCE},
            )
        return data

    def _fetch_valid(self, params: dict[str, Any]) -> dict[str, Any]:
        """Validate before the cache stores it, so a void or failed answer is never cached."""
        raw = self.fetch_raw(params)
        parse_elevation(raw)
        return raw

    def elevation_m(self, lat: float, lon: float) -> float:
        """SRTM GL1 elevation (m above the EGM96 geoid) at one point. One API call if not cached."""
        params = self.point_params(lat, lon)
        raw = self.cache.get_or_fetch(SOURCE, params, lambda: self._fetch_valid(params))
        return parse_elevation(raw)

    def terrain_sample(self, lat: float, lon: float) -> TerrainSample:
        """Elevation at the point and at its 4 neighbours one SRTM sample (~30 m) away.

        5 API calls for a new location (the free key allows ~50 a day), 0 once cached.
        Distances are in metres: one arc-second north-south is constant, east-west shrinks
        with cos(latitude) (~30.4 m in Costa Rica instead of ~30.9 m).
        """
        lat0, lon0 = snap_to_srtm_grid(lat), snap_to_srtm_grid(lon)
        step_rad = math.radians(ARCSEC_DEG)
        return TerrainSample(
            elevation_m=self.elevation_m(lat0, lon0),
            north_m=self.elevation_m(lat0 + ARCSEC_DEG, lon0),
            south_m=self.elevation_m(lat0 - ARCSEC_DEG, lon0),
            east_m=self.elevation_m(lat0, lon0 + ARCSEC_DEG),
            west_m=self.elevation_m(lat0, lon0 - ARCSEC_DEG),
            spacing_ns_m=EARTH_RADIUS_M * step_rad,
            spacing_ew_m=EARTH_RADIUS_M * step_rad * math.cos(math.radians(lat0)),
        )
