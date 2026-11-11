# app/api/AGENTS.md: HTTP layer

What the frontend talks to. The contract is [`docs/api-contract.yaml`](../../docs/api-contract.yaml).
General backend rules: [`backend/AGENTS.md`](../../AGENTS.md).

## Files
- `schemas.py`: Pydantic request/response models. **These are the contract in code.**
- `routes.py`: endpoint functions. `deps.py`: `Ctx` dependency (config + sources from `app.state`).
- `errors.py`: status per `ErrorCode`, error envelope, exception handlers, `X-Request-ID` middleware, error logging.

## Rules
- **Contract first.** Change `docs/api-contract.yaml` before the code, and agree it with the frontend.
  `tests/test_contract.py` fails if they differ. Never edit that test to make it pass.
- **Schema class names = OpenAPI component names.** Renaming a class is a breaking change.
- All schemas inherit `Schema` (`extra="forbid"`) so typos in requests fail loudly with 422.
- **Fields:** English `snake_case`, unit suffix (`temperature_c`), `Field(ge=..., le=...)` for ranges,
  `examples=[...]` on request fields (they show up in `/docs`), `description` when the meaning isn't obvious.
- **Prefer additive changes** (new optional fields). Removing or renaming fields breaks the frontend:
  call it out in the PR.
- **Routes are thin**, about 5 lines: take `ctx: Ctx` and the request, call `app.services`, return a schema.
  No business logic, no data fetching, no try/except here.
- **Errors** ([`docs/errors.md`](../../docs/errors.md)): `errors.py` here is the only place that builds
  error responses. Routes never `return JSONResponse(...)` for errors, never raise `HTTPException` and
  never `try/except`. Exceptions bubble up and become the standard envelope. Every route declares
  `responses=error_responses(...)` (500 always, 422 with input, 502/503 if it fetches data).
- Every route has a `response_model`, a `tags=[...]` and a docstring (shown in Swagger).
- Sync `def` routes are fine (FastAPI runs them in a thread pool). Use `async def` only with async I/O end to end.

## Adding an endpoint
Claude Code: `/new-endpoint`. By hand: contract → schemas → route → logic in `services.py` or `domain/`
→ happy path in `tests/test_api.py`, error paths in `tests/test_errors.py` → `make check`.
