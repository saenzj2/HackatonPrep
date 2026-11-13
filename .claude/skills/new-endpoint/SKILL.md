---
name: new-endpoint
description: Add or change an HTTP endpoint in the Guardians of the Harvest backend, contract-first. Updates backend/docs/api-contract.yaml, then Pydantic schemas, route, service logic and tests, keeping tests/test_contract.py green.
argument-hint: <what the endpoint should do>
---

# Add or change an endpoint (contract first)

Request: `$ARGUMENTS`

## Steps
1. Read `backend/docs/api-contract.yaml`, `backend/app/api/schemas.py`, `backend/app/api/routes.py`
   and `backend/app/services.py`.
2. **Propose the contract change first**: path, method, request and response fields with units, and
   which `ErrorCode`s it can return (`backend/docs/errors.md`). Show it to the user as a short
   YAML snippet and **wait for approval**. The frontend depends on it.
   Prefer additive changes; renaming or removing fields breaks the frontend.
3. Edit `docs/api-contract.yaml`. Class names in `schemas.py` must equal component names.
   Use `extra="forbid"` (inherit from `Schema`). Field names are English snake_case with unit suffixes.
4. Implement:
   - schemas in `app/api/schemas.py`
   - a thin route in `app/api/routes.py` (use `Ctx`, `responses=error_responses(...)`, no try/except)
   - logic in `app/services.py` (orchestration) or `app/domain/` (pure computation)
5. Tests: happy path in `backend/tests/test_api.py`; every error path in `backend/tests/test_errors.py`
   with `assert_error`. A new failure kind = a new code: follow "Adding an error" in `docs/errors.md`.
6. Run `make check`. If `test_contract.py` fails, diff `app.openapi()` against the contract:
   ```bash
   cd backend && .venv/bin/python -c "import json; from tests.conftest import isolated_app; print(json.dumps(isolated_app().openapi()['components']['schemas']['<Name>'], indent=1))"
   ```
   Fix the code or the contract (the contract is the source of truth), never the test.
7. Summarize the contract change in 2 or 3 lines the user can paste to the frontend team.
