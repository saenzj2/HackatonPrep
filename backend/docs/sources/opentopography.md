# OpenTopography: Point Elevation API (SRTM GL1)

| Field | Value |
|---|---|
| **Used for** | Elevation and local slope for erosion risk (`TerrainSource`) |
| **Adapter** | `app/integrations/opentopography.py` |
| **Fixtures** | `tests/fixtures/opentopography/elevation_san_jose_{center,north,south,east,west}.json` (centre lat 9.93, lon −84.08, neighbours ±1″; fetched 2026-11-14) |
| **Status** | ⚙️ Adapter + `services.erosion_risk()`, wired in `build_sources()` (`Sources.terrain`, `MockTerrain` in mock mode); served by `GET /erosion` |

## Access
- Endpoint: `GET https://portal.opentopography.org/API/v1/elevation?latitude=&longitude=&dataset=SRTM_GL1&API_Key=`
- **One point per request.** No batch parameter (checked in the OpenAPI spec, `/apidocs/openapi.json`).
- Auth: **API key required**, sent as the `API_Key` query parameter. Free key from opentopography.org →
  MyOpenTopo. Configured as `OPEN_TOPOGRAPHY_KEY` in `backend/.env` (see `.env.example`).
- **Quota (free key): 50 calls / 24 h non-academic, 250 academic.** A new location costs 5 calls.
- Docs: https://portal.opentopography.org/apidocs/#/Public/getPointElevation
- License: SRTM is public domain (NASA/USGS). Cite "NASA SRTM GL1, via OpenTopography".

## Response
```json
{"Status": "Success", "Message": "Elevation successfully retrieved.", "Elevation": 1164.0,
 "Location": {"Latitude": 9.93, "Longitude": -84.08}, "Unit": "Meters",
 "VCRS_EPSG": "5773", "VCRS_WKT": "...", "Reference Dataset": "SRTM_GL1"}
```
- `Elevation`: metres above the EGM96 geoid (EPSG:5773). Used as is.
- The key is **not** echoed in the body. `Location` echoes the request rounded to 6 decimals.
- Rejected as `source_bad_data`: `Status` ≠ `Success`, non-numeric elevation, unit ≠ Meters,
  SRTM void (−32768).

## Coverage and resolution
- SRTM GL1: 1 arc-second grid (~30.9 m N-S, ~30.4 m E-W in Costa Rica), 60° N to 56° S. Costa Rica covered.
- Acquired in February 2000. Terrain changes since (landslides, earthworks) aren't reflected.
- Radar DEM: in dense forest the surface sits partly on the canopy, and steep valleys can have voids.

## How we use it (slope)
- The point is snapped to the nearest SRTM sample (whole arc-second), then the 4 neighbours one
  sample N/S/E/W are fetched: 5 calls, each cached separately (6-decimal cache key, no API key in it).
  Neighbours are computed in integer arc-seconds, so adjacent locations share cache entries.
- Cached points are reused in **every** mode, live included (SRTM never changes), so each point
  costs one call ever. HTTP 429 (daily quota used up) gets its own message.
- Slope % = 100 × √((ΔzEW / 2dx)² + (ΔzNS / 2dy)²), with dx = R·cos(lat)·1″ and dy = R·1″ in metres.
- Spec asked for a 3×3 grid (9 calls). We use the 4 direct neighbours to fit the daily quota (decisions.md).

## Gotchas
- The API key is in the URL: the adapter never uses `raise_for_status()` (its message contains the URL)
  and never puts the key in cache params or error messages. Tests check this.
- A 30 m slope is a local estimate: it can miss a steep field next to a flat road, or vice versa.
