"""NOAA CPC El Niño indices: RONI (official since 2026-02-01) and the legacy ONI.

Same three parts as nasa_power.py:
  1. `fetch_raw()`          HTTP only, returns the file's text.
  2. `parse_enso_index()`   pure: text → EnsoIndex (anomalies in °C, no conversion).
  3. `index()`              through JsonCache, so `cached` mode works offline.

The files are plain text, so the cache stores {"text": ...}. The cache key has no date (a dated
key would make the committed snapshot miss every new month). In `live` mode a copy fetched less
than MAX_AGE ago is reused without a request; after that JsonCache refetches (and falls back to
the last good copy on failure). `cached` mode serves the last saved copy whatever its age. NOAA
rewrites the whole file monthly and revises the last ~2 values (docs/sources/noaa_enso.md).
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Literal

import httpx

from app.cache import JsonCache
from app.domain.enso import SEASONS, EnsoIndex, EnsoSeason
from app.errors import SourceDataError, SourceUnavailableError

SOURCE = "noaa_enso"
# NOAA updates the files once a month, so one request per day per index is plenty in live mode
# (decisions.md 2026-11-15). Placeholder.
MAX_AGE = timedelta(days=1)
IndexName = Literal["RONI", "ONI"]
URLS: dict[IndexName, str] = {
    "RONI": "https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt",
    "ONI": "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt",
}
# Anomalies are °C; real values stay within about ±3. Anything this large is a fill or a typo.
MAX_ABS_ANOMALY_C = 10.0


def parse_enso_index(text: str, name: str) -> EnsoIndex:
    """NOAA CPC index text → EnsoIndex. Rows are `SEAS YR [TOTAL] ANOM` (RONI has 3 columns, ONI 4:
    the anomaly is always the last). The first line is the header.

    Example input (RONI):
        SEAS   YR  ANOM
        DJF  1950 -1.19
    """
    lines = [line.split() for line in text.splitlines() if line.strip()]
    if len(lines) < 2 or lines[0][:2] != ["SEAS", "YR"]:
        raise SourceDataError(
            f"Unexpected NOAA {name} file: no 'SEAS YR' header", details={"source": SOURCE}
        )
    seasons = []
    for row in lines[1:]:
        try:
            season, year, anomaly = row[0], int(row[1]), float(row[-1])
        except (IndexError, ValueError) as e:
            raise SourceDataError(
                f"Unexpected NOAA {name} row {' '.join(row)!r}", details={"source": SOURCE}
            ) from e
        if season not in SEASONS or len(row) < 3:
            raise SourceDataError(
                f"Unexpected NOAA {name} row {' '.join(row)!r}", details={"source": SOURCE}
            )
        if abs(anomaly) >= MAX_ABS_ANOMALY_C:
            raise SourceDataError(
                f"NOAA {name} has an impossible value {anomaly} for {season} {year}",
                details={"source": SOURCE, "season": season, "year": year},
            )
        seasons.append(EnsoSeason(season=season, year=year, anomaly_c=anomaly))
    return EnsoIndex(name=name, seasons=tuple(seasons))


class NoaaEnso:
    name = SOURCE

    def __init__(self, cache: JsonCache, client: httpx.Client | None = None) -> None:
        self.cache = cache
        self.client = client or httpx.Client(timeout=30.0)

    def fetch_raw(self, index: IndexName) -> dict[str, Any]:
        try:
            resp = self.client.get(URLS[index])
            resp.raise_for_status()
            text = resp.text
        except httpx.HTTPStatusError as e:
            raise SourceUnavailableError(
                f"NOAA CPC answered HTTP {e.response.status_code}",
                details={"source": SOURCE, "status": e.response.status_code},
            ) from e
        except httpx.HTTPError as e:
            raise SourceUnavailableError(
                f"NOAA CPC request failed ({type(e).__name__})", details={"source": SOURCE}
            ) from e
        return {"text": text}

    def _fetch_valid(self, index: IndexName) -> dict[str, Any]:
        """Validate before the cache stores it, so a bad file never replaces a good copy."""
        raw = self.fetch_raw(index)
        parse_enso_index(raw["text"], index)
        return raw

    def index(self, name: IndexName) -> EnsoIndex:
        """The whole index, 1950 → latest season. Raises SourceUnavailableError,
        SourceDataError or CacheMissError."""
        params = {"index": name}
        # A copy under MAX_AGE old is reused in every mode: get_or_fetch alone would download the
        # whole file twice (RONI + ONI) on every live /plan-risk request.
        raw = self.cache.peek_fresh(SOURCE, params, MAX_AGE)
        if raw is None:
            raw = self.cache.get_or_fetch(SOURCE, params, lambda: self._fetch_valid(name))
        text = raw.get("text") if isinstance(raw, dict) else None
        if not isinstance(text, str):
            raise SourceDataError(
                f"Cached NOAA {name} entry has no text", details={"source": SOURCE}
            )
        return parse_enso_index(text, name)
