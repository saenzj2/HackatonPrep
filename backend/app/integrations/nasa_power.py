"""NASA POWER adapter (climatology + daily series): TEMPLATE for every other source.

Pattern to copy:
  1. `fetch_raw()`  does the HTTP call only and returns the raw JSON.
  2. `parse_*()`    is a pure function from raw JSON to a domain model, with unit conversion.
                    It is tested against a real saved response in tests/fixtures/<source>/.
  3. The public method goes through JsonCache so `cached` mode works offline.

API docs: https://power.larc.nasa.gov/docs/services/api/temporal/climatology/
          https://power.larc.nasa.gov/docs/services/api/temporal/daily/
Dataset notes: docs/sources/nasa_power.md
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

import httpx
import pandas as pd

from app.cache import JsonCache
from app.domain.models import MonthlyClimate
from app.errors import SourceDataError, SourceUnavailableError

SOURCE = "nasa_power"
BASE_URL = "https://power.larc.nasa.gov/api/temporal/climatology/point"
PARAMETERS = ("T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR")
MONTH_KEYS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")
# Mean days per month (Feb averaged over leap years) to turn mm/day into mm/month.
DAYS_IN_MONTH = (31, 28.25, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31)

DAILY_SOURCE = "nasa_power_daily"  # own cache namespace: daily requests never mix with climatology
DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
# T2M is the daily MEAN; T2M_MAX / T2M_MIN are that day's true max / min (needed for heat-stress
# and frost-day counts, docs/indicators.md). Changing this tuple changes the daily cache key.
DAILY_PARAMETERS = ("T2M", "T2M_MAX", "T2M_MIN", "PRECTOTCORR")
# POWER parameter → DataFrame column, both in the units below.
DAILY_COLUMNS = {
    "T2M": "temperature_c",
    "T2M_MAX": "temperature_max_c",
    "T2M_MIN": "temperature_min_c",
    "PRECTOTCORR": "rainfall_mm",
}
# Units POWER declares in the response's `parameters.<PARAM>.units` with community=AG.
# The parser does no conversion, so any other unit is rejected instead of silently mislabeled.
DAILY_UNITS = {"T2M": "C", "T2M_MAX": "C", "T2M_MIN": "C", "PRECTOTCORR": "mm/day"}
POWER_DATE_FORMAT = "%Y%m%d"  # POWER keys and start/end are YYYYMMDD

# Daily history for POST /plan-risk (replaying a planting against every past year).
# Separate parameters, params builder and cache namespace so it never touches daily_weather's keys.
HISTORY_SOURCE = "nasa_power_daily_history"
# IMERG_PRECTOT: NASA GPM IMERG satellite rain (~0.1°), the rain the engine uses.
# PRECTOTCORR: MERRA-2 rain (~0.5°), kept only to report how far it differs from IMERG.
# GWETROOT: root-zone soil wetness from the MERRA-2 land model (~0.5°), 0 dry .. 1 saturated.
HISTORY_PARAMETERS = ("IMERG_PRECTOT", "PRECTOTCORR", "T2M_MAX", "T2M_MIN", "GWETROOT")
HISTORY_COLUMNS = {
    "IMERG_PRECTOT": "rainfall_mm",
    "PRECTOTCORR": "rainfall_merra2_mm",
    "T2M_MAX": "temperature_max_c",
    "T2M_MIN": "temperature_min_c",
    "GWETROOT": "root_wetness",
}
# Units declared by POWER with community=AG (checked live 2026-11-15, docs/sources/nasa_power.md).
# GWETROOT is declared as "1": a dimensionless 0..1 fraction. No conversion is done.
HISTORY_UNITS = {
    "IMERG_PRECTOT": "mm/day",
    "PRECTOTCORR": "mm/day",
    "T2M_MAX": "C",
    "T2M_MIN": "C",
    "GWETROOT": "1",
}
# IMERG_PRECTOT is only served with time-standard=UTC: in the default local solar time (LST) every
# value is the -999 fill (checked live 2026-11-15). Days are therefore UTC days (Costa Rica is
# UTC-6, so a "day" runs 18:00 to 18:00 local); fine for multi-day windows, noted in the docs.
HISTORY_TIME_STANDARD = "UTC"


def parse_climatology(raw: dict[str, Any]) -> MonthlyClimate:
    """POWER climatology JSON → MonthlyClimate (°C, mm/month).

    T2M_MAX / T2M_MIN in the climatology are monthly means of the daily max / min.
    """
    try:
        params = raw["properties"]["parameter"]
        fill = raw.get("header", {}).get("fill_value", -999.0)
        t2m = [float(params["T2M"][m]) for m in MONTH_KEYS]
        t2m_max = [float(params["T2M_MAX"][m]) for m in MONTH_KEYS]
        t2m_min = [float(params["T2M_MIN"][m]) for m in MONTH_KEYS]
        prec_mm_day = [float(params["PRECTOTCORR"][m]) for m in MONTH_KEYS]
    except (KeyError, TypeError, ValueError) as e:
        raise SourceDataError(
            f"Unexpected NASA POWER payload ({type(e).__name__}: {e})", details={"source": SOURCE}
        ) from e
    if any(v == fill for v in t2m + t2m_max + t2m_min + prec_mm_day):
        raise SourceDataError(
            "NASA POWER returned fill values (no data for this point)", details={"source": SOURCE}
        )
    return MonthlyClimate(
        temperature_c=tuple(round(v, 2) for v in t2m),
        rainfall_mm=tuple(round(v * d, 1) for v, d in zip(prec_mm_day, DAYS_IN_MONTH, strict=True)),
        temperature_max_c=tuple(round(v, 2) for v in t2m_max),
        temperature_min_c=tuple(round(v, 2) for v in t2m_min),
    )


def _check_daily_units(raw: dict[str, Any], units: Mapping[str, str], source: str) -> None:
    """Reject a response whose declared units differ from `units` (no conversion is done).

    POWER lists units under the top-level `parameters` key. A payload without that metadata is
    accepted as is: the request always asks for community=AG, whose units are the expected ones.
    """
    declared = raw.get("parameters")
    if not isinstance(declared, dict):
        return
    for param, expected in units.items():
        meta = declared.get(param)
        unit = meta.get("units") if isinstance(meta, dict) else None
        if unit is not None and unit != expected:
            raise SourceDataError(
                f"NASA POWER daily {param} is in {unit!r}, expected {expected!r}",
                details={"source": source, "parameter": param},
            )


def parse_daily(raw: dict[str, Any]) -> pd.DataFrame:
    """POWER daily JSON → DataFrame, one row per day, columns:
    date, temperature_c, temperature_max_c, temperature_min_c, rainfall_mm.

    temperature_c: daily mean air temperature at 2 m (T2M, native °C).
    temperature_max_c / temperature_min_c: that day's maximum / minimum air temperature at 2 m
    (T2M_MAX / T2M_MIN, native °C). True daily extrema, not derived from the mean.
    rainfall_mm: that day's total precipitation (PRECTOTCORR, native mm/day, so no conversion).
    Days the source has no data for (fill value, normally -999) become NaN per variable instead of
    fake numbers; only a series with no data at all is rejected.

    Example input (trimmed):
        {"properties": {"parameter": {"T2M": {"20260101": 22.43, ...},
                                      "T2M_MAX": {"20260101": 27.06, ...},
                                      "T2M_MIN": {"20260101": 19.48, ...},
                                      "PRECTOTCORR": {"20260101": 1.38, ...}}},
         "header": {"fill_value": -999.0, ...}}
    Example output:
              date  temperature_c  temperature_max_c  temperature_min_c  rainfall_mm
        2026-01-01          22.43              27.06              19.48         1.38
    """
    _check_daily_units(raw, DAILY_UNITS, DAILY_SOURCE)
    try:
        # The values live under properties.parameter, one {YYYYMMDD: value} dict per variable.
        params = raw["properties"]["parameter"]
        # The number POWER uses for "no data" (normally -999), read from the header.
        fill = float(raw.get("header", {}).get("fill_value", -999.0))
        # One column per variable, one row per date key. Building it from the dicts (instead of
        # .keys() / .values() lists) makes pandas match rows by date, so a day missing from one
        # variable can't shift the other column. dtype=float fails fast on non-numeric values.
        df = pd.DataFrame(
            {column: params[param] for param, column in DAILY_COLUMNS.items()}, dtype=float
        )
        # The index is still the "20260101" strings; turn them into real dates.
        df.index = pd.to_datetime(df.index, format=POWER_DATE_FORMAT)
    except (KeyError, TypeError, ValueError) as e:
        # KeyError: a field is missing. TypeError: wrong shape (e.g. a list instead of a dict).
        # ValueError: a value isn't a number or a date isn't YYYYMMDD. All mean "unusable payload".
        raise SourceDataError(
            f"Unexpected NASA POWER daily payload ({type(e).__name__}: {e})",
            details={"source": DAILY_SOURCE},
        ) from e
    # Replace every fill value with NaN, so pandas aggregations (mean, sum…) skip it
    # instead of counting -999 °C or -999 mm as a real measurement.
    df = df.mask(df == fill)
    # A few missing days are fine, but no data at all (point outside coverage, or dates
    # too recent for POWER) is an error the caller should see.
    if df.empty or bool(df.isna().all().all()):
        raise SourceDataError(
            "NASA POWER returned only fill values (no daily data for this point and period)",
            details={"source": DAILY_SOURCE},
        )
    # Oldest day first, then move the dates from the index into a normal "date" column.
    return df.sort_index().rename_axis("date").reset_index()


def parse_daily_history(raw: dict[str, Any]) -> pd.DataFrame:
    """POWER daily history JSON → DataFrame, one row per (UTC) day, columns:
    date, rainfall_mm, rainfall_merra2_mm, temperature_max_c, temperature_min_c, root_wetness.

    rainfall_mm: GPM IMERG daily rain (IMERG_PRECTOT, native mm/day, no conversion).
    rainfall_merra2_mm: MERRA-2 daily rain (PRECTOTCORR, native mm/day), for comparison only.
    temperature_max_c / temperature_min_c: daily max / min air temperature at 2 m (native °C).
    root_wetness: root-zone soil wetness (GWETROOT, native 0..1 fraction).
    Fill values (-999, e.g. IMERG's last ~2 months) become NaN per variable. Only a variable with
    no data at all is rejected: the engine needs every column.
    """
    _check_daily_units(raw, HISTORY_UNITS, HISTORY_SOURCE)
    try:
        params = raw["properties"]["parameter"]
        fill = float(raw.get("header", {}).get("fill_value", -999.0))
        # Built from the {date: value} dicts so rows align by date across variables.
        df = pd.DataFrame(
            {column: params[param] for param, column in HISTORY_COLUMNS.items()}, dtype=float
        )
        df.index = pd.to_datetime(df.index, format=POWER_DATE_FORMAT)
    except (KeyError, TypeError, ValueError) as e:
        raise SourceDataError(
            f"Unexpected NASA POWER daily history payload ({type(e).__name__}: {e})",
            details={"source": HISTORY_SOURCE},
        ) from e
    df = df.mask(df == fill)
    empty = [str(c) for c in df.columns if bool(df[c].isna().all())]
    if df.empty or empty:
        raise SourceDataError(
            "NASA POWER daily history has no data for: "
            + (", ".join(empty) or "any variable")
            + " (IMERG rain needs time-standard=UTC)",
            details={"source": HISTORY_SOURCE, "empty_columns": empty},
        )
    return df.sort_index().rename_axis("date").reset_index()


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

    @staticmethod
    def daily_request_params(lat: float, lon: float, start: date, end: date) -> dict[str, Any]:
        """Query string for the daily endpoint. It is also the cache key, so the same
        point and period always map to the same cached file."""
        # Rounded to 2 decimals like request_params: nearby clicks share one cache entry.
        # community=AG returns agriculture-oriented units (°C, mm/day).
        return {
            "parameters": ",".join(DAILY_PARAMETERS),
            "community": "AG",
            "latitude": round(lat, 2),
            "longitude": round(lon, 2),
            "start": start.strftime(POWER_DATE_FORMAT),
            "end": end.strftime(POWER_DATE_FORMAT),
            "format": "JSON",
        }

    @staticmethod
    def history_request_params(lat: float, lon: float, start: date, end: date) -> dict[str, Any]:
        """Query string (and cache key) for the daily history. Same rounding as the others."""
        return {
            "parameters": ",".join(HISTORY_PARAMETERS),
            "community": "AG",
            "latitude": round(lat, 2),
            "longitude": round(lon, 2),
            "start": start.strftime(POWER_DATE_FORMAT),
            "end": end.strftime(POWER_DATE_FORMAT),
            "time-standard": HISTORY_TIME_STANDARD,
            "format": "JSON",
        }

    def fetch_raw(self, params: dict[str, Any], url: str = BASE_URL) -> dict[str, Any]:
        try:
            resp = self.client.get(url, params=params)
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

    def _fetch_valid_daily(self, params: dict[str, Any]) -> dict[str, Any]:
        """Call the daily endpoint and check the answer is usable before it gets cached."""
        raw = self.fetch_raw(params, url=DAILY_URL)
        # Parse once only to validate: if it raises, nothing is cached and live mode falls back
        # to an older good copy. The cache stores the raw JSON, not the DataFrame.
        parse_daily(raw)
        return raw

    def daily_weather(self, *, lat: float, lon: float, start: date, end: date) -> pd.DataFrame:
        """Daily mean, max and min temperature (°C) and rainfall (mm/day), start to end inclusive.

        Returns one row per day with columns date, temperature_c, temperature_max_c,
        temperature_min_c, rainfall_mm (see parse_daily). Missing values are NaN per variable.
        Arguments are keyword-only: daily_weather(lat=9.93, lon=-84.08, start=..., end=...).

        Raises SourceUnavailableError (API down or error status), SourceDataError (unusable
        answer) or CacheMissError (cached mode and this request was never fetched live).
        """
        params = self.daily_request_params(lat, lon, start, end)
        # The cache decides based on data_mode: cached → read the saved copy only;
        # live → call the API (via _fetch_valid_daily) and save it,
        # or reuse the saved copy if the call fails.
        raw = self.cache.get_or_fetch(DAILY_SOURCE, params, lambda: self._fetch_valid_daily(params))
        # Cached or fresh, the result always goes through the same parser.
        return parse_daily(raw)

    def _fetch_valid_history(self, params: dict[str, Any]) -> dict[str, Any]:
        """Fetch the history and validate it before it is cached (bad data never replaces good)."""
        raw = self.fetch_raw(params, url=DAILY_URL)
        parse_daily_history(raw)
        return raw

    def daily_history(self, *, lat: float, lon: float, start: date, end: date) -> pd.DataFrame:
        """Daily IMERG rain, MERRA-2 rain (mm/day), max/min temperature (°C) and root-zone
        wetness (0..1), start to end inclusive, for replaying a planting against past years.

        One request covers the whole range (26 years ≈ 0.8 MB, ~2 s). Columns: see
        parse_daily_history. Missing values are NaN per variable.

        Raises SourceUnavailableError, SourceDataError or CacheMissError like daily_weather.
        """
        params = self.history_request_params(lat, lon, start, end)
        raw = self.cache.get_or_fetch(
            HISTORY_SOURCE, params, lambda: self._fetch_valid_history(params)
        )
        return parse_daily_history(raw)
