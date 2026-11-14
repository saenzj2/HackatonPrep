# Error guide

**Mandatory for all backend code.** `tests/test_error_policy.py` and `tests/test_errors.py` enforce
it in CI, and ruff checks the exception-handling rules. If a check fails, follow this guide. Don't loosen the check.

- Catalog (every exception class): [`app/errors.py`](../app/errors.py)
- HTTP translation (the only place that builds error responses): [`app/api/errors.py`](../app/api/errors.py)

## The response every client gets

Every error response (4xx and 5xx, our errors, validation errors, 404s, crashes) has the same shape:

```json
HTTP 422
X-Request-ID: 7f3a9c1e2b4d
{
  "error": {
    "code": "out_of_region",
    "message": "Location (40.0, -3.7) is outside the MVP region 'Costa Rica'",
    "details": {"lat": 40.0, "lon": -3.7, "bbox": [-86.0, 8.0, -82.5, 11.3]},
    "request_id": "7f3a9c1e2b4d"
  }
}
```

| Field | Meaning | Stable? |
|---|---|---|
| `code` | what went wrong, machine-readable | **Yes**: part of the API contract |
| `message` | plain-English explanation, safe to show to users | No: wording may change |
| `details` | extra machine-readable context. Keys depend on the code (table below). `{}` if none | Keys per code are stable |
| `request_id` | same as the `X-Request-ID` header. Quote it in bug reports to find the log line | — |

## Error codes

| Code | HTTP | Raised by | When | `details` |
|---|---|---|---|---|
| `validation_failed` | 422 | HTTP layer | request body or query doesn't match the schema (wrong type, out of range, missing, unknown field, bad JSON) | `fields: [{loc, message, type}]` |
| `out_of_region` | 422 | `OutOfRegionError` | lat/lon outside the MVP region bbox (`config/mvp.yaml`) | `lat`, `lon`, `bbox` |
| `unknown_crop` | 422 | `UnknownCropError` | a crop id isn't in the catalog | `unknown`, `available` |
| `invalid_priorities` | 422 | `InvalidPrioritiesError` | all priority weights are 0 | `priorities` |
| `invalid_rotation` | 422 | `InvalidRotationError` | `current_rotation` doesn't have exactly one crop per season | `expected_length`, `seasons`, `got` |
| `not_found` | 404 | HTTP layer | no such route | — |
| `method_not_allowed` | 405 | HTTP layer | wrong HTTP method (see the `Allow` header) | — |
| `http_error` | 4xx | HTTP layer | any other HTTP-level error from the framework | — |
| `source_unavailable` | 502 | `SourceUnavailableError` | external source down, timed out or answered non-2xx | `source`, `status`? |
| `source_bad_data` | 502 | `SourceDataError` | source answered but the data is unusable (shape, fill values, bad rows) | `source` or `file`, `line` |
| `cache_miss` | 503 | `CacheMissError` | `data_mode=cached` and this request was never fetched in `live` | `source` |
| `config_invalid` | 500 | `ConfigError` | `mvp.yaml`, `.env` or a local data file is invalid. Normally stops startup | (hidden) |
| `domain_invariant` | 500 | `DomainInvariantError` | domain logic got impossible inputs: a bug upstream | (hidden) |
| `internal_error` | 500 | HTTP layer | any unexpected exception: a bug | (hidden) |

For `config_invalid`, `domain_invariant` and `internal_error`, clients only see a generic message and
empty `details`. The real message and traceback go to the log with the `request_id`.

## Rules for backend code

### Raising
1. **Raise only concrete classes from `app/errors.py`.** Never `ValueError`, `RuntimeError`, `Exception`,
   `HTTPException`, or the abstract bases `AppError` / `InvalidInputError` / `SourceError`.
   - Only exception: inside a Pydantic `@field_validator` / `@model_validator`, raise `ValueError`.
     Pydantic turns it into `validation_failed` (or `config_invalid` via `load_mvp_config`).
2. **Pick by who can fix it.** Is it the caller's input? Use an `InvalidInputError` subclass. An external
   source? Use a `SourceError` subclass. Our config or a bug? Use `ConfigError` / `DomainInvariantError`.
3. **Always chain:** `raise SourceDataError(...) from e`. Never lose the original exception (ruff `B904`).
4. **`message`**: one plain-English sentence a user could read. Say what's wrong and, if possible, how
   to fix it. **Never include** secrets, tokens, full URLs (they may carry API keys), file contents or tracebacks.
5. **`details`**: small, JSON-serializable, machine-readable (ids, values, limits). Keep keys stable for each
   code and document them in the table above. No secrets here either.

### Catching
6. **Catch the narrowest exception you can actually handle**, at the layer that can handle it.
   - Adapters catch library errors (`httpx.HTTPError`, `KeyError`, …) and translate them to `SourceError` subclasses.
   - Catching a base class to *recover* is fine (the cache catches `SourceError` to fall back to a cached copy).
7. **Never** use bare `except:`, `except Exception` (outside `app/api/errors.py`), or `except …: pass`
   that swallows errors silently (ruff `E722`, `BLE001`, `S110`).
8. **Don't catch to re-raise unchanged**, and don't catch in routes. Errors bubble up to `app/api/errors.py`.

### Logging
9. **Log once, at the boundary.** `app/api/errors.py` logs every error response: 4xx at INFO (no
   traceback), 5xx at ERROR with traceback and `request_id`. Elsewhere: **raise, don't log-and-raise**.
   - Exception: if you *handle* an error and continue (e.g. cache fallback), log a WARNING saying so.
10. Use `logging` with `%s` placeholders, not f-strings (ruff `G004`), and never `print`.

### HTTP layer
11. **Only `app/api/errors.py` builds error responses.** Routes never return `JSONResponse` for errors and
    never raise `HTTPException`. They let exceptions bubble.
12. **Every route declares its errors** with `responses=error_responses(...)`: 500 always, 422 if it takes
    input, 502/503 if it fetches data. Swagger and the contract then document them.

## Adding an error

1. Need a new **kind** of failure that the client should handle differently? Add a code. If the existing
   code fits, reuse it with a clear message and `details`.
2. In `app/errors.py`: add the `ErrorCode` member and a concrete class under the right base, with `code = ...`.
3. In `app/api/errors.py`: add the code to `STATUS_BY_CODE`, and to `PUBLIC_SERVER_CODES` if it's a 5xx whose message is safe.
4. In this guide: add a row to the **Error codes** table (code, status, class, when, details).
5. In `docs/api-contract.yaml`: add the value to the `ErrorCode` enum and tell the frontend.
6. In `tests/test_errors.py`: add a request that triggers it and asserts the envelope with `assert_error`.
7. Run `make check`. `test_error_policy.py` fails until steps 2 to 6 are all done.

## Testing errors
- Assert the **class** (`pytest.raises(SourceDataError, match=...)`) or the **code**
  (`assert_error(r, 422, ErrorCode.UNKNOWN_CROP)`), never only the status or only the message.
- Every code a request can trigger has a case in `tests/test_errors.py`.

## For the frontend

```ts
type ApiError = {
  error: { code: ErrorCode; message: string; details: Record<string, unknown>; request_id: string }
}

// Switch on `code`, never parse `message`.
switch (err.error.code) {
  case "validation_failed":  // highlight err.error.details.fields[i].loc ("body.lat")
  case "out_of_region":      // "pick a point inside the region", draw details.bbox on the map
  case "unknown_crop":       // refresh the crop list from GET /crops
  case "cache_miss":         // demo mode: this location isn't preloaded, try another
  case "source_unavailable":
  case "source_bad_data":    // "data source temporarily unavailable, try again"
  default:                   // show err.error.message + request_id ("report this id")
}
```
CORS exposes `X-Request-ID`, so the frontend can read it from the response headers too.
