"""NASA POWER climatology adapter: TEMPLATE for every other source.

Pattern to copy:
  1. `fetch_raw()`  does the HTTP call only and returns the raw JSON.
  2. `parse_*()`    is a pure function from raw JSON to a domain model, with unit conversion.
                    It is tested against a real saved response in tests/fixtures/<source>/.
  3. The public method goes through JsonCache so `cached` mode works offline.

API docs: https://power.larc.nasa.gov/docs/services/api/temporal/climatology/
Dataset notes: docs/sources/nasa_power.md
"""

from __future__ import annotations

from typing import Any

import httpx

from app.cache import JsonCache
from app.domain.models import MonthlyClimate
from app.errors import SourceDataError, SourceUnavailableError

SOURCE = "nasa_power"
BASE_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"
PARAMETERS = ("T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR")
MONTH_KEYS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
# Mean days per month (Feb averaged over leap years) to turn mm/day into mm/month.
DAYS_IN_MONTH = (31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)


def parse_climatology(raw: dict[str, Any]) -> MonthlyClimate:
    """POWER climatology JSON → MonthlyClimate (°C, mm/month)."""
    try:
        params = raw["properties"]["parameter"]
        fill = raw.get("header", {}).get("fill_value", -999.0)
        t2m = [float(params["T2M"][m]) for m in MONTH_KEYS]
        prec_mm_day = [float(params["PRECTOTCORR"][m]) for m in MONTH_KEYS]
    except (KeyError, TypeError, ValueError) as e:
        raise SourceDataError(
            f"Unexpected NASA POWER payload ({type(e).__name__}: {e})", details={"source": SOURCE}
        ) from e
    if any(v == fill for v in t2m + prec_mm_day):
        raise SourceDataError(
            "NASA POWER returned fill values (no data for this point)", details={"source": SOURCE}
        )
    return MonthlyClimate(
        temperature_c=tuple(round(v, 2) for v in t2m),
        rainfall_mm=tuple(round(v * d, 1) for v, d in zip(prec_mm_day, DAYS_IN_MONTH, strict=True)),
    )


class NasaPowerClimate:
    name = SOURCE

    def __init__(self, cache: JsonCache, client: httpx.Client | None = None) -> None:
        self.cache = cache
        self.client = client or httpx.Client(timeout=30.0)

    @staticmethod
    def request_params(lat: float, lon: float) -> dict[str, Any]:
        # 2 decimals ≈ 1 km, far finer than POWER's ~0.5° grid, so it is a safe cache key.
        return {
            "parameters": ",".join(PARAMETERS),
            "community": "AG",
            "latitude": round(lat, 2),
            "longitude": round(lon, 2),
            "format": "JSON",
        }

    def fetch_raw(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self.client.get(BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            # Message carries no URL: future sources may put API keys in query strings.
            raise SourceUnavailableError(
                f"NASA POWER answered HTTP {e.response.status_code}",
                details={"source": SOURCE, "status": e.response.status_code},
            ) from e
        except httpx.HTTPError as e:
            raise SourceUnavailableError(
                f"NASA POWER request failed ({type(e).__name__})", details={"source": SOURCE}
            ) from e
        except ValueError as e:
            raise SourceDataError(
                "NASA POWER returned a non-JSON body", details={"source": SOURCE}
            ) from e
        if not isinstance(data, dict):
            raise SourceDataError(
                f"NASA POWER returned {type(data).__name__}, expected an object",
                details={"source": SOURCE},
            )
        return data

    def _fetch_valid(self, params: dict[str, Any]) -> dict[str, Any]:
        """Fetch and validate BEFORE the cache stores it, so bad data never replaces a good copy
        (a SourceDataError here makes live mode fall back to the cached copy instead)."""
        raw = self.fetch_raw(params)
        parse_climatology(raw)
        return raw

    def monthly_climate(self, lat: float, lon: float) -> MonthlyClimate:
        params = self.request_params(lat, lon)
        raw = self.cache.get_or_fetch(SOURCE, params, lambda: self._fetch_valid(params))
        return parse_climatology(raw)
