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

## 2026-11-14 — Crop schema v1: soil-health, nutrition and market traits (T3.1, #23)
- **Decision:** `data/ecocrop_subset.csv` gains `root_depth_m`, `is_cover_crop`, `forage_value`,
  `nutrition_density`, `mycorrhizal_affinity`, `nitrogen_demand`, `market_note` and `sources`. The four
  trait columns are 0..1 scores; the API sends each as `{"level": none|low|medium|high, "score": 0..1}`
  (`TraitValue`), so the frontend can show the word and the number on hover. The `Trait` API type
  builds it from the score (`level_for()`), and `tests/test_trait_levels.py` fails if any response
  declares a trait any other way. The loader rejects bad values at startup.
  `nitrogen_demand` and `sources` were added beyond the issue's list: rule #25 needs "heavy feeders"
  and #24 needs a citation per crop. Full spec: `docs/crop-schema.md`.
- **Why:** Rotation rules, badges and explanations need these traits, and keeping them in the CSV keeps
  crop knowledge out of Python.
- **Data status:** root depth from FAO-56 Table 22; the other traits are a team estimate, labelled as
  such in `sources`, until #24 cites them. Every row stays `verified=false`.
- **Alternatives considered:** words only in the data (scoring would need its own mapping); words only
  in the API (no number for a hover); separate `*_score` fields or a score map next to the words (the
  pair can drift apart); a separate trait file (two files to keep in sync).
- **Contract change:** `Crop` gains the same 8 fields, all required, and a new `TraitValue` schema. There
  is no frontend yet, so nothing breaks; review it with the frontend when it starts.
- **Also decided:** keep `nitrogen_demand`, keep the CSV name, leave long-cycle crops out of #24.
- **Revisit if:** #24 finds cited numeric values that need finer cutoffs than `LOW_BELOW` / `MEDIUM_BELOW`.

## 2026-11-14 — mypy follows the running interpreter (no `python_version` pin)
- **Decision:** Removed `python_version = "3.11"` from `[tool.mypy]`.
- **Why:** numpy 2.5 (pulled in by pandas) ships stubs with 3.12-only syntax, so a 3.12 venv failed `make lint`
  with "Type statement is only supported in Python 3.12 and greater". CI stays on 3.11 and resolves an older numpy.
- **Alternatives considered:** Pin `python_version = "3.12"` (misstates the supported minimum); cap numpy.
- **Revisit if:** CI and local Python versions diverge enough to give different mypy results.

## 2026-11-14 — Erosion risk from SRTM slope + NASA POWER daily rain
- **Decision:** New source OpenTopography `/v1/elevation`, dataset `SRTM_GL1`, key `OPEN_TOPOGRAPHY_KEY`.
  Slope from the point + its 4 direct neighbours (one SRTM sample, ~30 m) by central differences.
  Terrain risk: < 5 % low, 5–15 % medium, > 15 % high. Rainfall risk = worst of average mm/day,
  heavy days (≥ 30 mm) per 30 days and max daily mm (`RainfallThresholds`, overridable per call).
  Combined = terrain, raised one step only when rain is high (or medium rain on medium terrain stays
  medium); never below terrain. `services.erosion_risk()` returns the 8-field dict; no endpoint yet.
- **Why:** The free key allows 50 calls/day and the API returns one point per call: 5 calls per
  location instead of 9 for a 3×3 grid. Rates instead of totals make short and long periods comparable.
  Flat land with heavy rain is not high water-erosion risk, so rain alone raises flat land to medium at most.
- **Alternatives considered:** 3×3 grid with Horn's method (9 calls); `/globaldem` AAIGrid tile
  (1 call, but a different endpoint than the spec); RUSLE (needs soil erodibility and cover data we don't have).
- **Revisit if:** `agro-logic` review of the thresholds. `max_daily_mm` grows with period length, so a
  full year almost always reaches high; consider dropping it or scaling it. A soil source becomes available.

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

## 2026-11-14 — Frontend mock data = generated example responses (T1.2, #13)
- **Decision:** `docs/examples/*.json` hold real responses for one demo field (Alajuela, lat 10.0,
  lon −84.2), generated by `scripts/make_examples.py` from the app in `cached` mode on top of the NASA
  POWER fixture. `tests/test_examples.py` validates every file against the contract schemas.
- **Why:** The frontend can build against realistic data without running the backend, and the mock can't
  silently drift from the contract. Hand-written mocks would.
  The test also regenerates the examples in memory and fails if the committed files differ
  (`generated_at` is pinned so output is deterministic), and checks `format` keywords.
- **Tooling:** `backend/scripts/` is the home for dev scripts. It is type-checked by mypy and importable
  in tests (`pythonpath = ["."]`). New dev dependency `jsonschema>=4.18,<5` (already pulled in transitively).
- **Alternatives considered:** Hand-written JSON (drifts); `mock` mode output (fake climate, less realistic).
- **Revisit if:** The demo fields change (T1.4) or the frontend wants more fields than one.

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
