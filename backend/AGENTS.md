# backend/AGENTS.md

Rules for all code under `backend/`. Project context: root [`AGENTS.md`](../AGENTS.md).
Each main folder has its own `AGENTS.md` with rules specific to it:

| Folder | Rules file covers |
|---|---|
| [`app/domain/`](app/domain/AGENTS.md) | pure scoring logic, dataclasses, determinism |
| [`app/integrations/`](app/integrations/AGENTS.md) | adapters, units, errors, caching, how to add a source |
| [`app/api/`](app/api/AGENTS.md) | routes, schemas = contract, status codes, how to add an endpoint |
| [`tests/`](tests/AGENTS.md) | fixtures, mocking HTTP, markers, naming |

**Error handling for every folder: [`docs/errors.md`](docs/errors.md)** (mandatory, CI-enforced).

## Layers (imports only flow downward)
```
app/main.py           app factory (create_app), CORS, startup checks
app/api/              routes.py (thin), schemas.py (Pydantic = contract), deps.py
app/services.py       orchestration: integrations → domain → schemas. Only place that knows all layers.
app/integrations/     one adapter per source + registry (__init__.build_sources) + protocols (base.py)
app/cache/            JsonCache: on-disk cache used by every network adapter
app/domain/           PURE logic. Imports nothing from the other app layers (except app/errors.py).
app/settings.py       EnvSettings (.env) + MvpConfig (config/mvp.yaml), validated at startup
app/errors.py         THE error catalog: ErrorCode + every exception class (pure stdlib, any layer may import)
app/api/errors.py     THE error → HTTP translation: status per code, envelope, request id, logging
```

## Units (normalized at the adapter boundary)
°C · mm (monthly totals or per crop cycle, say which) · pH · m³/m³ volumetric soil moisture · scores 0..1.
Adapters convert native units; the domain never converts. Put the unit in the name: `temperature_c`,
`rainfall_mm`, `moisture_m3m3`, `cycle_days`.

## Python practices

**Enforced by tools** (`make lint` = ruff + `mypy --strict`, also in pre-commit and CI). Don't
silence them with `# noqa` or `# type: ignore` unless there's no clean fix. Add a comment saying why.
- Type hints on every function, including the return type. `X | None`, not `Optional[X]`. Built-in generics (`list[str]`).
- `pathlib.Path`, never `os.path`. Timezone-aware datetimes (`datetime.now(UTC)`). `logging`, never `print`.
- No mutable default arguments. No bare `except:`. Exception names end in `Error`.

**By convention** (reviewers check these):
- **Data types.** Use `@dataclass(frozen=True)` for domain values and Pydantic `BaseModel` only at the
  edges (API schemas, config). Don't pass raw `dict`s between layers.
- **Errors.** Follow [`docs/errors.md`](docs/errors.md), always. Raise only concrete classes from
  `app/errors.py`, chain with `from e`, catch only what you can handle, log once at the boundary,
  never swallow. Enforced by `tests/test_error_policy.py` + ruff (`BLE`, `TRY`, `S110`, `B904`).
- **Functions.** Small, one job. More than 3 or 4 parameters → make them keyword-only (`*,`).
  Prefer pure functions; isolate I/O at the edges.
- **Names.** Descriptive English, units as suffixes, no abbreviations except standard ones
  (`lat`, `lon`, `ph`). Booleans read like questions (`is_legume`, `viable`).
- **Docstrings.** Every module gets one line on what it's for. Public functions get one where the "why"
  or the units aren't obvious. Comments explain why, not what.
- **Constants.** Module-level `UPPER_CASE`, with a comment on their source or that they're placeholders.
- **Imports.** No side effects at import time (no network, no file reads except in `create_app`).
  `from __future__ import annotations` at the top of modules that use type hints.
- **Dependencies.** Add them to `pyproject.toml` with a minimum version. Ask the team before adding heavy ones.
- **Config.** Read settings through `app/settings.py`. Never `os.environ` scattered in code, never hardcoded scope.

## Scoring constants
`MONOCULTURE_PENALTY`, `SAME_FAMILY_PENALTY`, `LEGUME_BONUS`, `HEAVY_AFTER_HEAVY_PENALTY`,
`FUNGI_BREAK_PENALTY` (rotation_rules.py), `STRONG_CATEGORY` (ranking.py) and
`GENERIC_SOIL_MOISTURE`, `HEAT_MARGIN_C`, `FROST_C`, `FROST_SAFE_C`, `MARGINAL_SCORE` (suitability.py),
`SLOPE_MEDIUM_PCT`, `SLOPE_HIGH_PCT`, `HEAVY_RAIN_MM` and `RainfallThresholds` defaults (erosion.py)
are placeholders. Change them only with a `docs/decisions.md` entry, ideally after an `agro-logic` review.
