---
name: new-source
description: Build a new data source adapter for the Guardians of the Harvest backend (climate, soil or crop data), following the NASA POWER template, with fixture-based tests, caching and registry wiring. Use after /explore-dataset has documented the source.
argument-hint: <source name>
---

# Add a data source adapter

Source: `$ARGUMENTS`

## Preconditions (Definition of Ready). Check them first.
- `backend/docs/sources/<name>.md` exists with units and an example request.
- A real response is saved in `backend/tests/fixtures/<name>/`.
If either is missing, run the `/explore-dataset` steps first (or ask the user).

## Steps
1. Read `backend/AGENTS.md`, `backend/app/integrations/base.py` and the template
   `backend/app/integrations/nasa_power.py` + its tests in `backend/tests/test_integrations.py`.
2. Pick the protocol: `ClimateSource`, `SoilSource` or `CropSource`. If the data doesn't fit any of
   them, **stop and propose** a domain model change to the user instead of bending the protocol.
3. Create `backend/app/integrations/<name>.py` with the same 3 parts:
   - `parse_<thing>(raw) -> <domain model>`: pure, converts to normalized units (°C, mm, pH, m³/m³),
     raises `SourceDataError` on bad payloads and fill values.
   - `fetch_raw(params)`: HTTP via an injectable `httpx.Client`; network/non-2xx → `SourceUnavailableError`,
     non-JSON → `SourceDataError`, always `from e`, `details={"source": ...}`, no URLs in messages.
   - Read `backend/docs/errors.md` first. Never raise built-ins or define exception classes in the adapter.
   - public protocol method that goes through `JsonCache.get_or_fetch("<name>", params, ...)`.
   - a class attribute `name = "<name>"` (it shows up in responses as `data_sources`).
4. Tests in `backend/tests/test_integrations.py` (or `test_<name>.py` if large):
   parse the real fixture (assert a known value and the unit conversion), reject fill values,
   `respx` for live → cached, live failure → cache fallback, cached miss, plus one
   `@pytest.mark.network` real call. **No real network in normal tests.**
5. Wire it in `backend/app/integrations/__init__.py::build_sources` for `live`/`cached`.
   Keep the mock for `mock` mode.
6. Update `backend/docs/sources/<name>.md` (Adapter + Status ✅) and add a
   `backend/docs/decisions.md` entry.
7. Run `make check`. Then smoke-test with
   `DATA_MODE=live backend/.venv/bin/python -c "..."` or `make dev` + curl, only if the user agrees to network calls.
8. Summarize: files changed, units conversion, what's still mocked.
