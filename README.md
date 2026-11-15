# Guardians of the Harvest 🌱🛰️

**NASA Space Apps Challenge 2026 — "Field Shift: Adapting Farms with NASA Data"**

> Guardians of the Harvest helps farmers compare crop rotation options by combining NASA Earth
> observation data with soil and crop information to identify more resilient agricultural strategies.

This repo holds the **backend** (Python + FastAPI). The frontend's location (a `frontend/` folder here
or a separate repo) is still to be decided. `backend/` is self-contained, so it can be moved either way.

**New to the team?** Read the [shared project context](PROJECT_CONTEXT.md) for the challenge,
participants, data-source candidates, provisional MVP status and 14–15 November local event plan.
For the selected San Carlos example, start with the [visual pilot baseline](docs/pilot-baseline/README.md):
six attributed images, what each dataset does (and does not) show, and the next farmer-facing steps.

## Quickstart

Want a no-install interactive satellite/evidence preview? Start the independent
[local MVP preview](tools/local-mvp-preview/README.md):
`python tools/local-mvp-preview/serve.py` → **http://127.0.0.1:8765**.
It is offline/local-only, separate from the team frontend; no San Carlos ranking is invented.

Requirements: **Python ≥ 3.11** (macOS: `brew install python@3.12`), `make`, `git`.

```bash
git clone git@github.com:saenzj2/HackatonPrep.git && cd HackatonPrep
make setup      # creates backend/.venv, installs deps, installs git hooks, copies .env.example → .env
make dev        # http://localhost:8000/app/ (frontend) and /docs (API)
make check      # ruff + mypy + tests: exactly what CI runs
```

Run `make` with no arguments to list every command.

**Windows:** use WSL, or Git Bash plus GNU make (Git for Windows does not include `make`; for example
`winget install ezwinports.make`, then reopen Git Bash). The Makefile uses the Windows venv layout
(`backend/.venv/Scripts/`) automatically. If the Microsoft Store opens or Python ≥ 3.11 is not found,
pass the interpreter explicitly: `make setup PYTHON=py` (Windows launcher) or the full `python.exe` path.

### What starts today

| Part | Start | Status |
|------|-------|--------|
| Backend API | `make dev` → http://localhost:8000/docs | Works with mock data out of the box |
| Local MVP preview | `python tools/local-mvp-preview/serve.py` → http://127.0.0.1:8765 | Independent offline explorer, not the team frontend |
| Frontend (skeleton) | `make dev` → http://localhost:8000/app/ | Static page served by the API; the real UI is issue #14. Start with [`backend/docs/frontend-guide.md`](backend/docs/frontend-guide.md) |
| Production | **https://terracosmos.space** | One Railway service. Merge to `main` (or **Actions → Deploy**) to deploy: [`docs/deploy.md`](docs/deploy.md) |

### Try it

```bash
curl -s -X POST localhost:8000/recommendations \
  -H 'Content-Type: application/json' \
  -d '{"lat": 10.0, "lon": -84.2, "crops": ["rice", "beans", "maize"],
       "priorities": {"water": 0.4, "soil": 0.3, "climate": 0.3}}'
```

Out of the box the API answers with **real data from the cache** (`data_mode: cached`): NASA POWER
climate, OpenLandMap soil pH, NASA SMAP soil moisture and FAO EcoCrop crop ranges. A committed
snapshot (`backend/app/cache/snapshots/`) covers the demo points (San Carlos 11.0, −84.6 and
Alajuela 10.0, −84.2); other points answer `503 cache_miss` until fetched once in `live` mode.

## How it works

```
Farmer picks location + candidate crops + priorities
        │
        ▼
Frontend ──POST /recommendations──► API (backend/app/api)
                                     │
                     ┌───────────────┼────────────────┐
                     ▼               ▼                ▼
              Climate source    Soil source      Crop source       backend/app/integrations
              (NASA POWER)      (mock in every  (EcoCrop CSV)     one adapter per source,
                                 data mode)                        same interface, cached
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
| `cached` | serves only from the cache (then the committed snapshot), never touches the network (**default, use for the demo**) |
| `live`   | fetches on every request, saves valid responses; falls back to cache on source errors |
| `mock`   | deterministic fake data, no network (tests only)                     |

Soil uses real data in `cached` and `live`: pH from OpenLandMap, monthly moisture from NASA SMAP
(`backend/docs/sources/smap.md`). `make cache-snapshot` copies newly fetched points into the snapshot. NASA POWER monthly normals feed
conditions and ranking; the daily-weather adapter exists but is not connected to those services.
The optional `current_rotation` request now enables comparison with a farmer-supplied baseline,
including score deltas, benefits, risks, evidence and data gaps (contract `0.2.0-draft`).
The farmer does **not** need a current crop: omit `current_rotation` for recommendations without
a baseline; omit `crops` to use configured candidates (an empty list is invalid). `crops` selects
candidates, not proof of what is growing. If a farmer supplies existing crops, the current comparison
accepts supported catalog IDs **one per configured season**, not an arbitrary single-crop baseline.
The intended flow includes advice for existing crops and alternatives only when supported by evidence;
the current heuristic model does not establish validated crop-specific advice. Unsupported crops or
insufficient evidence are gaps, not permission to invent alternatives. Pineapple at San Carlos is one
hypothetical example, not exclusive scope or a supported crop claim. See
[the two entry paths](PROJECT_CONTEXT.md#two-entry-paths-one-evidence-standard); changes to request
fields, crop-cycle assumptions or response behavior require contract-first agreement.

**Preferred direction: cache first, live only explicitly configured/allowed.** The implemented default
remains `mock`; `cached` never calls the network and returns `cache_miss` (503) for missing/unreadable
data. `live` is not cache-first, and there is no shared freshness/quota preflight. Do not silently
switch modes on a miss or hide stale data, mock inputs or incomplete evidence. The
[proposed cache policy and quota boundary](PROJECT_CONTEXT.md#cache-first-direction-and-quota-boundaries)
distinguishes current behavior from follow-up implementation, including the OpenTopography limit
identified in open PR #66, not a NASA POWER-wide 50/day limit.

The current endpoints take a representative **point**, not a selected rectangle or polygon average.
External Sentinel-2, WorldCover, SoilGrids and FTW research images are not backend integrations.

## Repo map

| Path | What |
|------|------|
| `frontend/` | Static frontend skeleton served at `/app` (replace freely, keep `index.html`) |
| `Dockerfile`, `.github/workflows/deploy.yml` | Production image and deploy ([`docs/deploy.md`](docs/deploy.md)) |
| `backend/app/api/` | HTTP routes and request/response schemas |
| `backend/app/domain/` | Suitability scoring and rotation ranking (pure Python, no I/O) |
| `backend/app/integrations/` | One adapter per data source (NASA POWER, EcoCrop, soil, mock) |
| `backend/app/cache/` | On-disk cache so the demo doesn't depend on the internet |
| `backend/config/mvp.yaml` | MVP scope (region, crops, variables, weights) |
| `backend/docs/api-contract.yaml` | **API contract** (OpenAPI), the agreement with the frontend |
| `backend/docs/frontend-guide.md` | **Frontend guide**: every endpoint and field, real examples, errors, how to display each piece, TS types |
| `backend/docs/errors.md` | **Error guide** (mandatory): codes, envelope, rules, frontend handling |
| `backend/docs/decisions.md` | Log of technical decisions |
| `backend/docs/sources/` | One page per dataset: variables, units, coverage, license |
| `backend/tests/fixtures/` | Real sample responses from each source |
| `docs/pilot-baseline/` | Curated San Carlos visual evidence, source attribution and research limitations |
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
6. **Demo safety.** Reuse suitable cached evidence first. Acquire only agreed missing requests with
   explicit live configuration/authorization and a checked budget, then switch to `cached`. Verify both
   cache-hit and cache-miss behavior before presenting; a miss must not trigger hidden live calls.

### Adding a data source (by hand)

1. Write `backend/docs/sources/<name>.md` (template in `.claude/skills/explore-dataset/SKILL.md`).
2. Save one real response in `backend/tests/fixtures/<name>/`.
3. Add `backend/app/integrations/<name>.py` that implements the matching protocol in `integrations/base.py`.
   Use `nasa_power.py` as the template.
4. Add a test that uses the fixture (no real network). Register the source in `integrations/__init__.py`.

Claude Code users can run `/new-source` to do the same thing. Not using Claude Code? See section 3b of
[`learning/harness-cheatsheet.md`](learning/harness-cheatsheet.md) to get the same benefits with any editor or AI tool.

## Use of AI tools (Space Apps SI disclosure)

Parts of this repository's code, tests and documentation were written with AI coding assistants
(Anthropic Claude Code and OpenAI Codex). The `.claude/` folder, `CLAUDE.md` and `AGENTS.md` hold the
instructions those tools followed. Every change went through a pull request, CI (lint, type checks,
tests) and team review. Crop data comes from FAO EcoCrop, and climate, soil and moisture data come
from NASA POWER, NASA SMAP, NASA GPM IMERG, MERRA-2 and OpenLandMap. None of it is AI-generated,
and no AI model produces the recommendations: every score comes from the code in `backend/app/domain/`.

AI-generated media and text, each labeled where it appears:

| What | AI tool | Label |
|---|---|---|
| Background video clips (web app and presentation video) | Veo (Google) | "AI generated video" on screen |
| Logo and brand artwork | AI image generator | "AI generated" in the app footer and on the project page |
| Presentation video end card | Claude (Anthropic) | Labeled in the video |
| Glossary and practice-card texts (`backend/data/*.json`) | Claude (Anthropic) | Note in the app; reviewed by the team |
| Project backlog | Claude (Anthropic) | Reviewed by the team |

The web app lists the same items on its Learn page ("How we used AI").
Submission notes: [`docs/submission.md`](docs/submission.md).
