# Harness cheatsheet: Guardians of the Harvest backend

Everything the backend harness includes, on one page. Layers 1 and 2 apply to everyone.
Layer 3 is for people using Claude Code. Not using it? Section **3b** shows how to get the same benefits.

---

## 0. First time

```bash
brew install python@3.12        # any Python ≥ 3.11 works
make setup                      # venv + deps + git hooks + backend/.env from .env.example
make dev                        # http://localhost:8000/docs
```

---

## 1. Base for everyone (tools that enforce the rules)

### Commands (`make` from the repo root)
| Command | What it does |
|---|---|
| `make` | list every command |
| `make setup` | first-time setup (fails clearly if Python < 3.11) |
| `make dev` | API with auto-reload on :8000. Swagger UI at `/docs` |
| `make test` | fast tests, no network (~0.3 s) |
| `make test-all` | also runs `@pytest.mark.network` tests that call real APIs |
| `make fmt` | auto-format + auto-fix lint |
| `make lint` | ruff check + format check + mypy strict (changes nothing) |
| `make check` | **lint + tests = exactly what CI runs. Run before every PR.** |
| `make clean` | delete venv and caches |

### What runs automatically
| When | What | Config |
|---|---|---|
| every `git commit` | ruff (fix + format), mypy, YAML/JSON check, end-of-file and whitespace fixes, large-file guard, private-key detector, **block commits to `main`** | `.pre-commit-config.yaml` |
| every PR and push to `main` | `make install` → `make lint` → `make test` on Python 3.11 | `.github/workflows/ci.yml` |

### Code quality rules enforced by tools
- **ruff**: style, imports, naming (`N`), bug patterns (`B`), pathlib (`PTH`), timezone-aware dates (`DTZ`),
  no `print` (`T20`), type annotations (`ANN`), pytest style (`PT`), pylint subset (`PL`), and more. Config in `backend/pyproject.toml`.
- **mypy --strict** on `backend/app/`, with the pydantic plugin.
- **`tests/test_contract.py`**: the app must match `backend/docs/api-contract.yaml`.
- **`tests/test_architecture.py`**: `domain/` can't import api/integrations/httpx/pydantic, and so on.
- **`tests/test_error_policy.py` + `tests/test_errors.py`**: the error guide (section 2b) is followed everywhere.
- **`config/mvp.yaml` validation**: weights must sum to 1, seasons can't overlap, crops must exist. Bad config stops the server at startup.

---

## 2. Rules and context for humans and any AI assistant

`AGENTS.md` files are read by Cursor, Copilot, Codex and Claude Code. Each `CLAUDE.md` just imports its `AGENTS.md`.

| File | What's in it |
|---|---|
| `AGENTS.md` (root) | challenge, MVP sentence, scope principle, roles, data flow, commands, workflow, **Definition of Ready / Done**, don'ts |
| `backend/AGENTS.md` | layers, units, **Python best practices** (tool-enforced + conventions), scoring constants |
| `backend/docs/errors.md` | **error guide**: codes, envelope, raising/catching/logging rules, frontend handling |
| `backend/app/domain/AGENTS.md` | pure logic: no I/O, deterministic, explainable rules, keyword-only args |
| `backend/app/integrations/AGENTS.md` | adapter pattern (fetch → parse → cache), units, errors, adding a source |
| `backend/app/api/AGENTS.md` | contract first, schema = component names, thin routes, status codes, adding an endpoint |
| `backend/tests/AGENTS.md` | no real network, real fixtures, `match=` on raises, naming, markers |
| `CLAUDE.md` (root) | imports `AGENTS.md` + Claude-only notes (skills, subagents, hooks, never commit) |

### The rules in 10 lines
1. **Contract first.** Change `backend/docs/api-contract.yaml`, agree it with the frontend, then the code.
2. **Scope is config.** Region, crops, variables, weights and seasons live in `backend/config/mvp.yaml`, never in code.
3. **Branch per feature**, small PRs, `make check` green.
4. **Log decisions** in `backend/docs/decisions.md`, including any `mvp.yaml` change.
5. **Units in names** (`temperature_c`, `rainfall_mm`, `moisture_m3m3`), converted only in adapters.
6. **`domain/` is pure.** No I/O, same input → same output.
7. **Tests never hit the network** (except `@pytest.mark.network`). Fixtures are real saved responses.
8. **No secrets in git.** Keys go in `backend/.env`, names (no values) in `.env.example`.
9. **The demo runs on `data_mode: cached`.**
10. **No heavy dependencies** (GDAL, xarray…) without asking.

### 2b. Error guide (`backend/docs/errors.md`), mandatory everywhere
| Rule | In practice |
|---|---|
| One catalog | every exception class and `ErrorCode` lives in `backend/app/errors.py` |
| Raise only catalog classes | never `ValueError`/`RuntimeError`/`HTTPException` (Pydantic validators excepted) |
| Pick by who can fix it | caller → `OutOfRegionError`, `UnknownCropError`, `InvalidPrioritiesError` · source → `SourceUnavailableError`, `SourceDataError`, `CacheMissError` · us → `ConfigError`, `DomainInvariantError` |
| Always chain | `raise X(...) from e` |
| Safe messages | plain English, no secrets/URLs/tracebacks; context goes in `details` |
| Catch narrowly | no `except Exception`, no `except: pass`, no try/except in routes |
| Log once | `app/api/errors.py` logs 4xx at INFO, 5xx at ERROR with traceback; elsewhere raise, don't log-and-raise |
| One response shape | `{"error": {"code", "message", "details", "request_id"}}` + `X-Request-ID` header, for **every** error |
| New code | catalog → `STATUS_BY_CODE` → guide table → contract enum → `tests/test_errors.py` (the policy test fails until all are done) |

| Code | HTTP | Code | HTTP |
|---|---|---|---|
| `validation_failed` | 422 | `source_unavailable` | 502 |
| `out_of_region` | 422 | `source_bad_data` | 502 |
| `unknown_crop` | 422 | `cache_miss` | 503 |
| `invalid_priorities` | 422 | `config_invalid` | 500 |
| `not_found` | 404 | `domain_invariant` | 500 |
| `method_not_allowed` | 405 | `internal_error` | 500 |
| `http_error` | 4xx | | |

Frontend: switch on `error.code`, never parse `message`. Show `request_id` in "report a bug".

### Definition of Ready → Definition of Done
- **Ready:** contract agreed · real fixture saved · `docs/sources/<x>.md` with units · known `mvp.yaml` dependency
- **Done:** `make check` green · tests for new logic · explicit units · contract = code · `decisions.md` updated

---

## 3. Claude Code extras (`.claude/`)

### Skills (type them in Claude Code)
| Skill | Use it to |
|---|---|
| `/explore-dataset <name or URL>` | evaluate a dataset → `docs/sources/<name>.md` + a real fixture (no code) |
| `/new-source <name>` | build an adapter + tests + cache + registry wiring (NASA POWER pattern) |
| `/new-endpoint <description>` | contract → schemas → route → tests, and asks you before changing the contract |
| `/demo-check [lat,lon …]` | full checks + warm cache + offline proof → go/no-go list |

### Subagents (ask: "use the X agent to …")
| Agent | Does | Can edit? |
|---|---|---|
| `nasa-data` | researches NASA/EO datasets: variables, units, resolution, Costa Rica coverage, access | no |
| `agro-logic` | reviews agronomic sense of scoring, crop ranges, seasons | no |
| `reviewer` | reviews your branch diff against AGENTS.md / DoD before a PR | no |

### Hooks (automatic)
| When | What |
|---|---|
| after Claude edits a `backend/**/*.py` | `ruff format` + `ruff check --fix`. Leftover errors go back to Claude to fix |
| when Claude finishes a turn with backend changes | fast tests (including the error policy). Failures go back to Claude to fix |

### Permissions (`.claude/settings.json`)
- **Allowed without asking:** `make …`, venv `pytest`/`ruff`/`uvicorn`, read-only git (`status`, `diff`, `log`, `show`), `git switch/checkout -b/worktree`, local `curl`, NASA POWER fetches.
- **Asks first:** `git add` and anything not listed here.
- **Always denied:** `git commit`, reading or editing `.env`, `rm -rf`, `git push --force`, `git reset --hard`, `git clean -fd`.
- Personal overrides go in `.claude/settings.local.json` (gitignored).
- Team rule (CLAUDE.md): **Claude never commits or pushes.** People do.

---

## 3b. Not using Claude Code? Get the same benefits

Sections 1 and 2 work the same for everyone: `make`, pre-commit, CI and the `AGENTS.md` rules don't depend
on any AI tool. Only `.claude/` is Claude-specific, and every piece of it has a manual equivalent.

### Your AI assistant already reads the rules
Most AI coding tools (Cursor, GitHub Copilot, OpenAI Codex and others) read `AGENTS.md` automatically,
including the ones inside subfolders. If yours doesn't, point it at the files: *"Follow `AGENTS.md`,
`backend/AGENTS.md` and `backend/docs/errors.md`"*. Mention the folder's own `AGENTS.md` too
(e.g. `backend/app/integrations/AGENTS.md`) when you work there.

### Replace the hooks
| Claude Code hook | Do this instead |
|---|---|
| ruff after every edit | format on save in your editor (VS Code snippet below), or run `make fmt` |
| fast tests at the end of a task | run `make test` before you commit. Pre-commit already runs ruff and mypy on every commit |

VS Code (`.vscode/settings.json`, personal; needs the Ruff and Python extensions):
```json
{
  "python.defaultInterpreterPath": "backend/.venv/bin/python",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": { "source.fixAll": "explicit", "source.organizeImports": "explicit" }
  },
  "python.testing.pytestEnabled": true,
  "python.testing.cwd": "${workspaceFolder}/backend"
}
```

### Skills and subagents are plain checklists and prompts
Every skill and subagent is a Markdown file you can read as a checklist, or paste into any AI chat as instructions.

| Claude Code | File | Use it without Claude Code |
|---|---|---|
| `/explore-dataset` | `.claude/skills/explore-dataset/SKILL.md` | follow the steps; the template at the bottom is the `docs/sources/<name>.md` format |
| `/new-source` | `.claude/skills/new-source/SKILL.md` | follow the steps, or paste it to your assistant with the source name |
| `/new-endpoint` | `.claude/skills/new-endpoint/SKILL.md` | same: contract → schemas → route → tests |
| `/demo-check` | `.claude/skills/demo-check/SKILL.md` | run its commands in order before a demo |
| `nasa-data` agent | `.claude/agents/nasa-data.md` | paste the text below the `---` header as a prompt, then ask your dataset question |
| `agro-logic` agent | `.claude/agents/agro-logic.md` | paste it as a prompt and attach `backend/app/domain/` + `config/mvp.yaml` |
| `reviewer` agent | `.claude/agents/reviewer.md` | before a PR: run `make check`, then paste it with `git diff main...HEAD` |

Ignore the `$ARGUMENTS` placeholders and the `---` front matter; they're for Claude Code.

### Guardrails you have to keep yourself
Claude Code blocks some actions in `.claude/settings.json`. Without it, these are on you:
- never commit `.env` or keys (pre-commit's private-key detector catches some, not all)
- no force-push to shared branches, no `rm -rf` on things you haven't checked
- `main` is protected by pre-commit: always work on a branch

### Before every PR (everyone)
`make check` → read the diff against the **Definition of Done** (section 2) → follow the error guide → push.

---

## 4. Backend map

```
backend/
├── config/mvp.yaml          ← MVP scope + data_mode (mock | live | cached)
├── data/ecocrop_subset.csv  ← crop ranges (approximate until verified=true)
├── docs/
│   ├── api-contract.yaml    ← API contract (draft v0, to review with the frontend)
│   ├── errors.md            ← error guide (mandatory)
│   ├── decisions.md         ← decision log
│   └── sources/             ← one page per dataset (nasa_power, ecocrop)
├── app/
│   ├── main.py              ← create_app(), CORS, startup checks
│   ├── errors.py            ← error catalog: ErrorCode + every exception class
│   ├── settings.py          ← .env + mvp.yaml, validated
│   ├── services.py          ← integrations → domain → response
│   ├── api/                 ← routes.py, schemas.py, deps.py, errors.py (error → HTTP)
│   ├── domain/              ← models.py, suitability.py, ranking.py (pure)
│   ├── integrations/        ← base.py (protocols), nasa_power.py (template), ecocrop.py, mock.py
│   └── cache/               ← JsonCache (backend/.cache/, gitignored)
└── tests/                   ← test_domain, test_api, test_errors, test_error_policy, test_contract,
                               test_integrations, test_config, test_architecture
```

### Endpoints
| Method | Path | Returns |
|---|---|---|
| GET | `/health` | status, version, data_mode, region |
| GET | `/crops` | MVP crops with temperature, rainfall and pH ranges |
| GET | `/conditions?lat=&lon=` | 12-month climate, per-season summary, soil |
| POST | `/recommendations` | ranked rotations with score, breakdown (climate, water, soil), explanation, notes |

Errors: always the envelope `{"error": {code, message, details, request_id}}`. Codes are in section 2b and `backend/docs/errors.md`.

### Data sources today
| Data | `mock` mode | `live` / `cached` mode |
|---|---|---|
| Temperature, rainfall | fake, deterministic | **NASA POWER** monthly climatology 2001–2025 |
| Soil pH, moisture | fake | **still fake** (SMAP / SoilGrids to evaluate) |
| Crop ranges | EcoCrop CSV | EcoCrop CSV |

### Data modes
- `mock`: no network, default, for frontend work
- `live`: real APIs, saves every response to the cache, falls back to the cache if the API fails
- `cached`: cache only, never the network. **Use this for the demo.**
- Switch with `data_mode:` in `mvp.yaml`, or per run: `DATA_MODE=live make dev`

---

## 5. Common recipes

| I want to… | Do |
|---|---|
| change crops / region / weights | edit `backend/config/mvp.yaml` → restart `make dev` → log it in `decisions.md` |
| try real NASA data | `DATA_MODE=live make dev` |
| prepare the demo | run `live` once per demo location, then `DATA_MODE=cached make dev` (or `/demo-check`) |
| add a data source | `docs/sources/<x>.md` → fixture → adapter like `nasa_power.py` → tests → `build_sources()` (or `/explore-dataset` + `/new-source`) |
| add or change an endpoint | contract → `schemas.py` → `routes.py` → `services.py` → `test_api.py` (or `/new-endpoint`) |
| raise or handle an error | read `backend/docs/errors.md`; new kind of failure → "Adding an error" steps |
| see why CI failed | run `make check` locally. Contract mismatch → `backend/.venv/bin/pytest backend/tests/test_contract.py` |
| work in parallel with Claude | `git worktree add ../hp-<task> -b feat/<task>` |

## 6. Known open items
- Error envelope is part of contract draft v0 → include it in the frontend review
- Region, crops and variables are **TBD** (team decision) → `mvp.yaml`
- API contract is **draft v0** → review with the frontend
- Soil data is **mocked** → SMAP / SoilGrids still to evaluate
- EcoCrop values are **approximate** (`verified=false`) → check against FAO EcoCrop
- Scoring v0 often gives several rotations close to 1.0 in mild climates → `agro-logic` review
- **Deployment: not set up yet** (the MVP runs locally). Options for a quick, free or cheap deploy are below.

### Quick deploy options (checked 2026-11-11; free tiers change often, so confirm on each pricing page)

| Platform | Free? | Good to know |
|---|---|---|
| **Render** (simplest) | Free web service tier | Sleeps after ~15 min idle; the first request then takes up to ~1 min. Deploys straight from GitHub |
| **Hugging Face Spaces** (Docker) | Free CPU Space | Needs a small Dockerfile; the app must listen on port **7860**. Public by default |
| **Google Cloud Run** | Monthly free allowance | Needs a billing account (card). Scales to zero, fast cold starts. Needs a Dockerfile |
| **Vercel** | Hobby plan (non-commercial) | Runs FastAPI as serverless functions; the disk is read-only (except `/tmp`), so `live` mode can't keep its cache |
| **Railway** | Trial credit only | Then paid; very easy GitHub deploys |
| **Heroku** | **No free tier** since 2022 | Eco dynos ~$5/month (sleep after 30 min idle). Students: check Heroku credits in the GitHub Student Developer Pack |
| **Fly.io**, **Koyeb** | Reportedly trial-only or no free plan for new users | Verify before choosing |

**What our backend needs on any host:**
- Start command, run from `backend/`: `uvicorn app.main:create_app --factory --host 0.0.0.0 --port $PORT`
  (Hugging Face: `--port 7860`). Install with `pip install -e .` from `backend/` (editable, so
  `config/` and `data/` are found; no dev extras needed).
- Env vars: `DATA_MODE=cached` for the demo, and `CORS_ORIGINS=<the deployed frontend URL>`.
- **The cache must ship with the app.** Free hosts wipe the disk on every deploy or restart, and
  `backend/.cache/` is gitignored. Before deploying, run `live` for the demo locations, then commit a copy
  of the cache (e.g. to `backend/demo-cache/`) and point `cache_dir` at it (`CACHE_DIR=demo-cache`).
- Free tiers sleep: open the URL a minute before presenting to wake it up.
