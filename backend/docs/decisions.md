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

## 2026-11-14 — pandas for daily NASA POWER data
- **Decision:** Add `pandas>=2.2` (and `pandas-stubs` for mypy) to the backend. The new
  `NasaPowerClimate.daily_weather()` returns a DataFrame (`date`, `temperature_c`, `rainfall_mm`).
  Daily fill values become NaN instead of rejecting the whole request.
- **Why:** Data retrieval and calculations (dry spells, heat waves, frost days, aggregations) are
  easier and clearer in pandas, which the team's data work already uses.
- **Alternatives considered:** Plain tuples in a frozen dataclass, like `MonthlyClimate` (no extra
  dependency, but every calculation is hand-written).
- **Revisit if:** `make setup` gets too slow, or the domain layer needs to stay pandas-free
  (convert DataFrames to domain models in `services.py` before they reach `app/domain/`).

## 2026-11-14 — Contract v0.2: compare against the farmer's current rotation, structured explanations
- **Decision:** `POST /recommendations` takes an optional `current_rotation` (one crop id per season).
  It is scored like every other combination and returned as `current_rotation` (its `rank` is its
  position among all combinations, so it can exceed `top_n`). Its crops join the candidate set.
  Every `Rotation` gains `is_current`, `score_delta_vs_current`, `benefits`, `risks`, `data_gaps` and
  `evidence`. `notes` is kept but deprecated (= benefits + risks). New error code `invalid_rotation`
  (422) when the length doesn't match the seasons. `MonthClimate` / `SeasonSummary` gain
  `temperature_max_c` / `temperature_min_c`. Additive only; `method_version` is now `suitability-v1`.
- **Why:** The challenge asks to compare at least three strategies *including the existing rotation*
  and to explain for each why it was suggested, the evidence, benefits, information gaps and risks.
- **Alternatives considered:** Replacing `notes` (breaks the frontend); letting the frontend find the
  baseline with `top_n=50` (fails when the farmer's crops aren't in `crops`).
- **Revisit if:** The frontend no longer reads `notes` (remove it), or seasons become configurable per request.

## 2026-11-14 — Same-family penalty in rotation scoring
- **Decision:** `SAME_FAMILY_PENALTY = 0.05` per transition between *different* crops of the same
  botanical family (e.g. rice → maize, both Poaceae), half of `MONOCULTURE_PENALTY` (0.10).
  A family change is listed as a benefit.
- **Why:** Crops of the same family share most pests and diseases, so the cycle isn't broken. Before
  this, rice → maize scored like a real rotation. Placeholder value, pending `agro-logic` review.
- **Revisit if:** An agronomist suggests per-family values, or pest data becomes available.

## 2026-11-14 — Heat stress and frost risk variables (mvp.yaml: variables)
- **Decision:** `heat` and `frost` added to `variables` in `mvp.yaml`, both in the climate category,
  using POWER `T2M_MAX` / `T2M_MIN` (monthly means of daily max/min), which were already fetched.
  - heat: season mean daily max vs the crop's absolute max temperature. 1 at or below it, linear to 0
    at `abs_max + HEAT_MARGIN_C` (6 °C).
  - frost: daily min of the season's coldest month. 0 at or below 0 °C, 1 from 5 °C (generic, all crops).
- **Why:** The challenge names heat stress and frost risk. No extra requests; cached data still works.
- **Alternatives considered:** Counting hot/frost days from daily POWER data (more requests, more
  accurate); per-crop frost limits (no reliable source yet).
- **Revisit if:** `agro-logic` review, or the pilot region includes highlands where frost matters.
  Frost scores 1 almost everywhere in lowland Costa Rica.

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
