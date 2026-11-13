---
name: demo-check
description: Pre-demo verification for Guardians of the Harvest. Runs all checks, confirms the API works fully offline in cached mode for the demo locations, and reports a go/no-go checklist. Use before any presentation, judging session or demo recording.
argument-hint: "[lat,lon ...] demo locations (default 10.0,-84.2)"
---

# Demo check

Demo locations: `$ARGUMENTS` (default `10.0,-84.2`). Report every step honestly; a red item is a
NO-GO until fixed or consciously accepted by the user.

## Steps
1. `git status`: warn about uncommitted changes or not being on the branch that will be demoed.
2. `make check`: lint + fast tests must be green.
3. Config sanity: print `region`, `crops`, `variables`, `seasons`, `data_mode` from
   `backend/config/mvp.yaml`. Flag anything still `TBD`, and crops with `verified=false` in
   `backend/data/ecocrop_subset.csv` (fine for a demo, but say so if a judge asks).
4. Warm the cache (**needs network; ask the user first**):
   for each location, call the services in `live` mode, for example
   ```bash
   cd backend && DATA_MODE=live .venv/bin/python -c "
   from fastapi.testclient import TestClient; from app.main import create_app
   c = TestClient(create_app())
   for lat, lon in [(10.0, -84.2)]:
       r = c.post('/recommendations', json={'lat': lat, 'lon': lon}); print(lat, lon, r.status_code)"
   ```
5. Offline proof: repeat the same calls with `DATA_MODE=cached`. Every location must return 200 and
   `data_sources.climate == "nasa_power"`. A 503 means that location isn't cached.
6. Start the real server the way it will run in the demo (`DATA_MODE=cached make dev`) in the
   background, then `curl -s localhost:8000/health` and one `POST /recommendations`. Stop the server after.
7. Report a checklist:
   - [ ] checks green · [ ] cache warm for N/N locations · [ ] offline responses OK
   - [ ] top rotation and explanation for each location (paste them, they're useful for the pitch)
   - [ ] open caveats (mocked soil, unverified crop values, TBD scope)
   And remind the user: set `data_mode: cached` (or `DATA_MODE=cached`) on the demo machine.
