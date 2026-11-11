# Technical decisions log

One entry per decision, newest first. Keep each to a few lines: **what**, **why**, and
what would make us revisit it. Changes to `config/mvp.yaml` go here too.

Template:

```
## YYYY-MM-DD — Short title
- **Decision:** …
- **Why:** …
- **Alternatives considered:** …
- **Revisit if:** …
```

---

## 2026-11-07 — Project-wide error guide, enforced
- **Decision:** `docs/errors.md` is mandatory. One catalog (`app/errors.py`: `ErrorCode` + classes),
  one HTTP translator (`app/api/errors.py`), one response envelope for every error
  (`{"error": {code, message, details, request_id}}`) plus the `X-Request-ID` header. Errors are logged once at the boundary.
- **Enforced by:** `tests/test_error_policy.py` (only catalog errors raised, no exception classes elsewhere,
  no hand-built error responses, codes ↔ HTTP status ↔ guide ↔ contract ↔ tests in sync, every route documents errors),
  `tests/test_errors.py` (every reachable code through the real app), ruff `BLE`, `TRY`, `S101`, `S110`, `S112`, `G`, `LOG`.
- **Why:** The frontend gets one predictable shape and switches on stable codes. Bugs are traceable by request id.
  Messages can't leak secrets or internals.
- **Contract change:** `ErrorResponse` was `{detail}`; now the envelope + `ErrorBody` + `ErrorCode` enum.
  Still draft v0, so it needs the frontend's review.

## 2026-11-06 — Stricter code quality tooling and per-folder rules
- **Decision:** ruff now also runs `N, C4, RET, PTH, DTZ, T20, ANN, PT, PL, RUF`; mypy `--strict`
  (pydantic plugin) on `app/` in `make lint`, pre-commit and CI; `tests/test_architecture.py` enforces
  layer imports. Each main folder has an `AGENTS.md` (+ `CLAUDE.md` importing it).
- **Why:** Rules checked by tools hold for every teammate and AI assistant. Prose alone drifts.
- **Changes it forced:** `CacheMiss` → `CacheMissError`, `InvalidRequest` → `InvalidRequestError`,
  `rank_rotations` is keyword-only.

## 2026-11-06 — Soil stays mocked in v0
- **Decision:** `SoilSource` uses `MockSoil` in every `data_mode`. Responses say so in `data_sources.soil = "mock"`.
- **Why:** No soil source has been chosen yet. Candidates: NASA SMAP for surface moisture
  (needs an Earthdata login and has coarse resolution) and ISRIC SoilGrids for pH (not NASA, but free REST API).
- **Revisit if:** the soil source evaluation is done. Use `/new-source` or the README steps.

## 2026-11-06 — Scoring method v0 (EcoCrop-style trapezoids)
- **Decision:** Per variable 0..1 trapezoid over EcoCrop ranges, grouped as climate (temperature),
  water (rainfall, soil moisture), soil (pH); priority-weighted mean; 0 if any variable is outside
  its absolute range. Rotation = one crop per season, cyclic; −0.10 for monoculture, +0.05 for legume
  after non-legume (split across transitions).
- **Why:** Simple, explainable to farmers and judges, and works with the few variables we have.
- **Known simplifications:** mean temperature only (no heat/frost days); crop-cycle rainfall = mean
  monthly season rainfall × cycle length; one generic soil-moisture range for every crop; bonus and
  penalty values are placeholders.
- **Revisit if:** The `agro-logic` review or an agronomist flags issues; when T2M_MAX/T2M_MIN are used.

## 2026-11-06 — Default seasons: primera (May to Aug) and postrera (Sep to Nov)
- **Decision:** Two rainfed seasons, dry season treated as fallow.
- **Why:** Standard Central American rainfed calendar; a rainfed dry-season crop fails on water in most
  of the Pacific slope, so every rotation would come out non-viable.
- **Revisit if:** The pilot region is on the Caribbean slope (no marked dry season) or irrigation is in scope.

## 2026-11-06 — NASA POWER climatology endpoint for temperature and rainfall
- **Decision:** Use `/api/temporal/climatology/point` (monthly normals 2001–2025, `AG` community)
  instead of daily data.
- **Why:** One small request per location (~1.5 KB), already aggregated to the monthly level the
  model uses. No API key. Daily data can be added later for extremes (heat days, dry spells).

## 2026-11-06 — Crop data as a local EcoCrop subset CSV
- **Decision:** `data/ecocrop_subset.csv`, versioned. Values marked `verified=false` until checked
  against the FAO EcoCrop source.
- **Why:** EcoCrop has no stable API, the data is small and static, and the demo must not depend on it.

## 2026-11-06 — Contract-first API with a CI check
- **Decision:** `docs/api-contract.yaml` is the agreement with the frontend. `tests/test_contract.py`
  fails if the app and the contract differ (endpoints, schema names, fields, required, params).
- **Why:** Frontend and backend work in parallel. Drift shows up in CI instead of at demo time.
- **Status:** Draft v0, still to be reviewed with the frontend.

## 2026-11-06 — Data modes: mock / live / cached
- **Decision:** `data_mode` in `config/mvp.yaml` (env `DATA_MODE` overrides). `live` writes every
  response to `backend/.cache/`; `cached` never touches the network. `live` falls back to the cache
  when a source fails.
- **Why:** The frontend gets realistic data from day 1, and the demo survives bad venue Wi-Fi.

## 2026-11-06 — Stack and tooling
- **Decision:** Python ≥ 3.11, FastAPI, Pydantic v2, httpx. venv + pip via `make setup`. ruff for
  lint and format, pytest, pre-commit, GitHub Actions.
- **Why:** The team knows Python and pandas. venv + pip needs no extra tool (team choice over uv).

## 2026-11-06 — Backend is self-contained in `backend/`
- **Decision:** All backend code, config, docs and its `pyproject.toml` live under `backend/`.
- **Why:** The frontend's location (same repo or separate) is still undecided. This way either option works.
