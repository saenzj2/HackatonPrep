# app/integrations/AGENTS.md: data source adapters

One module per external data source. Each turns a raw API or file into normalized domain models.
General backend rules: [`backend/AGENTS.md`](../../AGENTS.md).

## Files
- `base.py`: the protocols every adapter implements (`ClimateSource`, `SoilSource`, `CropSource`).
- `__init__.py`: `build_sources()` picks the adapter per data type from `data_mode`.
- `nasa_power.py`: **the template**. Copy its structure for new sources.
- `opentopography.py`: SRTM GL1 point elevation (API key, 5 calls per slope sample).
- `openlandmap.py`: OpenLandMap soil by depth via Google Earth Engine (`ee` imported lazily; 1 request per 250 m pixel).
- `smap.py`: NASA SMAP L4 root-zone moisture, 12 monthly means per point via Earth Engine (~30 s, cached forever).
- `measured_soil.py`: the real `SoilSource` for scoring: OpenLandMap pH (0–30 cm) + SMAP monthly moisture.
  Earth Engine setup and error handling are shared in `openlandmap.py` (`initialize_earth_engine`, `call_earth_engine`).
- `noaa_enso.py`: NOAA CPC El Niño indices (RONI official, ONI legacy), plain-text files cached as
  `{"text": ...}`; no dated cache key, a copy under `MAX_AGE` (1 day) is reused in `live` mode
  (`JsonCache.peek_fresh`).
- `ecocrop.py`: local CSV catalog. `mock.py`: deterministic fake data for `mock` mode.

## The adapter pattern (keep these three parts separate)
1. `fetch_raw(params) -> dict`: the HTTP call and nothing else. Use an injectable `httpx.Client`
   (tests pass their own) with an explicit timeout. Translate failures with `from e`: network, timeout
   or non-2xx → `SourceUnavailableError`; non-JSON or wrong type → `SourceDataError`.
   Check the payload's type before returning it.
2. `parse_<thing>(raw) -> DomainModel`: a pure module-level function. Converts units, rejects the
   source's fill/missing values and unexpected shapes with `SourceDataError`. Easiest part to test.
3. A public method implementing the protocol, routed through `JsonCache.get_or_fetch(namespace, params, fetch)`
   so `cached` mode works offline and `live` falls back to the cache on failure.

## Rules
- **Errors follow [`docs/errors.md`](../../docs/errors.md).** Put `details={"source": SOURCE, ...}` on every
  error. Messages never contain URLs (query strings can carry API keys). Missing local files → `ConfigError`.
- **Return domain models, never raw payloads.** Units are normalized here and nowhere else.
  Write the native unit and the conversion in a comment next to it.
- **Cache keys** = the request params, rounded to a sensible precision (lat/lon to 2 decimals).
- **Never call the network at import time** or in `__init__`. Only inside methods.
- **No secrets in code.** Keys come from `EnvSettings` (`backend/.env`), listed without values in `.env.example`.
- Every adapter has a class attribute `name` (it shows in API responses as `data_sources`).
- Keep the mock for every protocol in sync, so `mock` mode always works without network.
- Don't add GDAL, xarray or other heavy geospatial dependencies without asking the team. Prefer point APIs.

## Adding a source
Claude Code: `/explore-dataset` then `/new-source`. By hand:
1. `docs/sources/<name>.md` (variables, native units, resolution, coverage in the region, license).
2. One real response in `tests/fixtures/<name>/`.
3. The adapter, following the 3 parts above.
4. Tests: parse the fixture, `respx` for live → cached, fallback and miss, optional `@pytest.mark.network`.
5. Wire it in `build_sources()` for `live`/`cached`; add a `docs/decisions.md` entry.
