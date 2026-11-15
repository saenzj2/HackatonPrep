# AGENTS.md

Context for AI coding assistants (Claude Code, Cursor, Copilot, Codex…) and for humans who are new to the repo.
Backend-specific rules: [`backend/AGENTS.md`](backend/AGENTS.md).

## The project
- **Team:** Guardians of the Harvest. **Event:** NASA Space Apps Challenge 2026.
- **Challenge:** "Field Shift: Adapting Farms with NASA Data". Decision support that combines NASA
  Earth observation with soil, crop traits and farmer priorities to compare crop rotation strategies
  that improve soil health, save water and adapt to changing temperature, rain and extremes.
- **MVP in one sentence:** Guardians of the Harvest helps farmers compare crop rotation options by
  combining NASA Earth observation data with soil and crop information to identify more resilient
  agricultural strategies.

### Scope principle: 1 region + few crops + few variables + 1 clear recommendation
- 1 pilot region (likely Costa Rica, **TBD**), 3 to 5 crops (**TBD**), 3 to 5 variables, 1 simple
  ranking method, 1 results dashboard or map.
- All of this lives in `backend/config/mvp.yaml`. **Don't hardcode region, crops, variables or weights in code.**
- When in doubt, cut scope. A working demo with one region beats an unfinished global tool.

## Data flow
```
User: location + crops + priorities
  → Frontend → POST /recommendations
  → backend/app/api (validate) → app/services (orchestrate)
      → app/integrations: climate (NASA POWER), soil (mock for scoring; OpenLandMap profile via Earth Engine), crops (EcoCrop CSV), all cached
      → app/domain: suitability per crop/season → rotation ranking → explanation
  → JSON response → Frontend dashboard or map
```

## Repo layout
- `backend/`: FastAPI app, self-contained (has its own `pyproject.toml`, config, docs, tests)
- `learning/`: pre-hackathon practice material and team guides (e.g. `harness-cheatsheet.md`). **Not product code and not linted.**
- `.claude/`: Claude Code settings, skills and subagents (optional, ignored by other tools)

## Commands (run from repo root)
| Command | Does |
|---|---|
| `make setup` | venv + deps + git hooks (needs Python ≥ 3.11) |
| `make dev` | API on :8000, Swagger at `/docs` |
| `make test` | fast tests, no network |
| `make test-all` | includes `@pytest.mark.network` tests that call real APIs |
| `make fmt` / `make lint` | ruff format + fix / ruff check + mypy (no changes) |
| `make check` | lint + tests = what CI runs. **Must pass before a PR.** |

## Workflow
1. **Contract first.** API changes start in `backend/docs/api-contract.yaml`, agreed with the frontend.
2. **Branch per feature** (`feat/…`, `fix/…`, `docs/…`). Never commit to `main` (pre-commit blocks it).
3. **Small PRs**, CI green, at least one reviewer.
4. **Log decisions** in `backend/docs/decisions.md`, including any `mvp.yaml` change.
5. **Demo data** is always real and cached (`data_mode: cached`, the default; committed snapshot in
   `backend/app/cache/snapshots/`). `mock` is for tests only.

## Definition of Ready (before starting a task)
- [ ] The endpoint or field exists in the contract, or the contract change is agreed.
- [ ] For a new data source: one real response saved under `backend/tests/fixtures/<source>/` and a
      `backend/docs/sources/<source>.md` page with variables, **units**, resolution, coverage in the region, license.
- [ ] It's clear which `mvp.yaml` setting (if any) the change depends on.

## Errors: one guide, always
Every error in the backend follows [`backend/docs/errors.md`](backend/docs/errors.md): raise only the
classes in `backend/app/errors.py`, every API error uses the same `{"error": {code, message, details,
request_id}}` envelope, and errors are logged once at the HTTP boundary. CI enforces it
(`tests/test_error_policy.py`, `tests/test_errors.py`, ruff). Read the guide before writing a `raise` or `except`.

## Definition of Done
- [ ] `make check` passes locally and in CI.
- [ ] New logic has tests. Tests never call the real network (use fixtures + `respx`), except ones
      marked `@pytest.mark.network`.
- [ ] Units are explicit in names or docs (`temperature_c`, `rainfall_mm`, `moisture_m3m3`).
- [ ] Contract, schemas and `test_contract.py` agree.
- [ ] Errors follow `backend/docs/errors.md` (catalog classes only, codes documented, HTTP test per new code).
- [ ] `decisions.md` updated if a choice was made (source, method, scope, tooling).

## Don'ts
- Don't read, print or commit `.env` or any secret. Add new keys to `backend/.env.example` without values.
- Don't call external APIs in tests or at import time.
- Don't raise built-in exceptions or `HTTPException`, don't build error responses by hand, don't swallow errors.
- Don't put I/O or HTTP in `backend/app/domain/`.
- Don't change `mvp.yaml`, the contract or the scoring constants without a `decisions.md` entry.
- Don't add heavy dependencies (GDAL, xarray, geopandas…) without discussing it. Keep `make setup` fast.
- Don't modify teammates' practice files in `learning/` (new guides there are fine).

## Conventions
- English for code, docs, API fields and commit messages.
- Commits: `type(scope): summary` (`feat`, `fix`, `docs`, `chore`, `test`, `refactor`).
- Python ≥ 3.11. ruff (lint + format) and mypy `--strict` are enforced by `make lint`, pre-commit and CI.
  Python practices: `backend/AGENTS.md`. Folder-specific rules: the `AGENTS.md` inside each folder.
