---
name: explore-dataset
description: Evaluate a dataset or API (NASA or other) for the Guardians of the Harvest backend. Documents variables, units, resolution, coverage in the pilot region and license in backend/docs/sources/<name>.md and saves one real sample response as a test fixture. Use before writing any new data source adapter.
argument-hint: <dataset name or URL>
---

# Explore a dataset

Goal: decide if `$ARGUMENTS` is usable for the MVP, and leave behind everything needed to build an
adapter (Definition of Ready in AGENTS.md). **Do not write adapter code here.** That's `/new-source`.

## Steps
1. Read `backend/config/mvp.yaml` (region bbox, variables) and `backend/docs/sources/` (what exists).
2. Research the dataset. Consider delegating to the `nasa-data` subagent for NASA products.
   Find: access method (REST / file download / needs Earthdata login?), variables, **native units**,
   spatial and temporal resolution, period covered, latency, license and citation.
3. Make **one** small real request for a point inside the region bbox (default lat 10.0, lon −84.2).
   Save the raw response to `backend/tests/fixtures/<name>/<short_description>.json` (or .csv).
   Keep it under ~200 KB; trim if needed and note the trimming.
   If access needs credentials, stop and ask the user. Never read `.env`.
4. Write `backend/docs/sources/<name>.md` using the template below. Look at
   `backend/docs/sources/nasa_power.md` as a finished example.
5. Finish with a short verdict: **use / use with caveats / don't use**, and which `mvp.yaml`
   variable it would feed.

## Template
````markdown
# <Dataset name>

| Field | Value |
|---|---|
| **Used for** | <variable(s) and protocol: ClimateSource / SoilSource / CropSource> |
| **Adapter** | not yet (`app/integrations/<name>.py`) |
| **Fixture** | `tests/fixtures/<name>/<file>` (lat, lon, fetched YYYY-MM-DD) |
| **Status** | 🔍 Explored, verdict: <use / caveats / no> |

## Access
- Endpoint / download:
- Auth:
- Docs:
- License / citation:

Example request:
```
<exact URL or command>
```

## Variables
| Name | Meaning | Native unit | Convert to |
|---|---|---|---|

## Coverage and resolution
- Spatial:
- Temporal (period, frequency, latency):
- Pilot region (Costa Rica): <covered? gaps? clouds? resolution vs farm size?>

## Sample values (fixture)

## Gotchas
- <fill values, scaling factors, time zones, units per day vs per month…>

## Verdict and next steps
````
