# Guardians of the Harvest 🌱🛰️

**NASA Space Apps Challenge 2026 — "Field Shift: Adapting Farms with NASA Data"**

> Guardians of the Harvest helps farmers compare crop rotation options by combining NASA Earth
> observation data with soil and crop information to identify more resilient agricultural strategies.

This repo holds the **backend** (Python + FastAPI). The frontend's location (a `frontend/` folder here
or a separate repo) is still to be decided. `backend/` is self-contained, so it can be moved either way.

## Quickstart

Requirements: **Python ≥ 3.11** (macOS: `brew install python@3.12`), `make`, `git`.

```bash
git clone git@github.com:saenzj2/HackatonPrep.git && cd HackatonPrep
make setup      # creates backend/.venv, installs deps, installs git hooks, copies .env.example → .env
make dev        # API on http://localhost:8000 — interactive docs at http://localhost:8000/docs
make check      # ruff + mypy + tests: exactly what CI runs
```

Run `make` with no arguments to list every command. On Windows, use WSL or Git Bash.

### Try it

```bash
curl -s -X POST localhost:8000/recommendations \
  -H 'Content-Type: application/json' \
  -d '{"lat": 10.0, "lon": -84.2, "crops": ["rice", "beans", "maize"],
       "priorities": {"water": 0.4, "soil": 0.3, "climate": 0.3}}'
```

Out of the box the API answers with **realistic mock data** (`data_mode: mock`), so the frontend can
build against it from day 1. Real sources are plugged in one at a time.

## How it works

```
Farmer picks location + crops + priorities
        │
        ▼
Frontend ──POST /recommendations──► API (backend/app/api)
                                     │
                     ┌───────────────┼────────────────┐
                     ▼               ▼                ▼
              Climate source    Soil source      Crop source       backend/app/integrations
              (NASA POWER)      (mock → SMAP/    (EcoCrop CSV)     one adapter per source,
                                 SoilGrids)                         same interface, cached
                     └───────────────┼────────────────┘
                                     ▼
                       Suitability + rotation ranking            backend/app/domain (pure logic)
                                     ▼
                       Ranked rotations + explanation  ──► Frontend shows it
```

### Scope is configuration, not code

Region, crops, variables and priority weights live in [`backend/config/mvp.yaml`](backend/config/mvp.yaml).
When the team decides them, edit that file (and log why in
[`backend/docs/decisions.md`](backend/docs/decisions.md)). No code changes are needed.

`data_mode` in that file picks where data comes from:

| mode     | what it does                                                         |
|----------|----------------------------------------------------------------------|
| `mock`   | deterministic fake data, no network (default)                        |
| `live`   | calls real APIs and saves every response to the local cache          |
| `cached` | serves only from the cache, never touches the network (**use for the demo**) |

## Repo map

| Path | What |
|------|------|
| `backend/app/api/` | HTTP routes and request/response schemas |
| `backend/app/domain/` | Suitability scoring and rotation ranking (pure Python, no I/O) |
| `backend/app/integrations/` | One adapter per data source (NASA POWER, EcoCrop, soil, mock) |
| `backend/app/cache/` | On-disk cache so the demo doesn't depend on the internet |
| `backend/config/mvp.yaml` | MVP scope (region, crops, variables, weights) |
| `backend/docs/api-contract.yaml` | **API contract** (OpenAPI), the agreement with the frontend |
| `backend/docs/errors.md` | **Error guide** (mandatory): codes, envelope, rules, frontend handling |
| `backend/docs/decisions.md` | Log of technical decisions |
| `backend/docs/sources/` | One page per dataset: variables, units, coverage, license |
| `backend/tests/fixtures/` | Real sample responses from each source |
| `AGENTS.md` (+ one per main folder) | Rules for humans and AI assistants: context, layers, Python practices |
| `CLAUDE.md`, `.claude/` | Claude Code extras: settings, hooks, skills, subagents (optional) |
| `learning/harness-cheatsheet.md` | One-page summary of everything in this harness |
| `learning/` | Pre-hackathon practice material and team guides |

## Team workflow

1. **Contract first.** Changing an endpoint? Update `backend/docs/api-contract.yaml` first and agree
   on it with the frontend. CI fails if the code and the contract disagree.
2. **One branch per feature.** `main` is protected by a pre-commit hook. Use names like `feat/nasa-power`
   or `fix/rain-units`.
3. **Small PRs, CI must pass.** Run `make check` before pushing.
4. **Log decisions** in `backend/docs/decisions.md` (date, decision, why, who).
5. **Never commit secrets.** Keys go in `backend/.env` (gitignored). `backend/.env.example` lists them without values.
6. **Demo safety.** Before presenting, run once in `live` to fill the cache, then switch to `cached`.

### Adding a data source (by hand)

1. Write `backend/docs/sources/<name>.md` (template in `.claude/skills/explore-dataset/SKILL.md`).
2. Save one real response in `backend/tests/fixtures/<name>/`.
3. Add `backend/app/integrations/<name>.py` that implements the matching protocol in `integrations/base.py`.
   Use `nasa_power.py` as the template.
4. Add a test that uses the fixture (no real network). Register the source in `integrations/__init__.py`.

Claude Code users can run `/new-source` to do the same thing. Not using Claude Code? See section 3b of
[`learning/harness-cheatsheet.md`](learning/harness-cheatsheet.md) to get the same benefits with any editor or AI tool.
