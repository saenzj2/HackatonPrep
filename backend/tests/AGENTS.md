# tests/AGENTS.md: test suite

pytest. Run `make test` (fast, no network) or `make test-all` (includes real API calls).
General backend rules: [`backend/AGENTS.md`](../AGENTS.md).

## Files
| File | Tests |
|---|---|
| `conftest.py` | fixtures: `client`, `make_client(**config_overrides)`, `env`, `config`, `load_fixture()`, `contract_validator()` |
| `test_domain.py` | scoring and ranking (pure, no app) |
| `test_ecocrop_import.py` | EcoCrop import script; CSV ranges match the EcoCrop fixture |
| `test_real_soil.py` | SMAP moisture adapter (real fixtures, fake sampler) and `MeasuredSoil` |
| `test_planting_windows.py` | best sowing months per crop (toy climate) |
| `test_rotation_rules.py` | rotation rules: verdict and reason per crop pair |
| `test_api.py` | every endpoint's happy path through `TestClient` |
| `test_recommendations_contract.py` | `POST /recommendations` on the real NASA POWER fixture (`cached` mode) validated against the contract |
| `test_errors.py` | **every error response**: envelope, code, status, request id, logging (`assert_error`) |
| `test_error_policy.py` | static enforcement of `docs/errors.md` across `app/` |
| `test_architecture.py` | layer import rules |
| `test_contract.py` | app ↔ `docs/api-contract.yaml` agreement. **Don't edit it to make it pass.** |
| `test_integrations.py` | adapters: parse real fixtures, `respx` for HTTP, cache modes |
| `test_plan_risk.py` | plan stress test: each check just below / above its threshold, gaps, year crossing, aggregation (toy weather) |
| `test_noaa_enso.py` | NOAA RONI / ONI: parse the real files, cache modes, phase labels, the El Niño split, plan-risk without NOAA |
| `test_perennials.py` | permanent crops: year climate, minimum score, suitability words, notes, ranking |
| `test_plan_advice.py` | plan-risk actions per cause and alternatives (date shifts, other crops, ranking) |
| `test_daily_history.py` | NASA POWER daily history for `/plan-risk` (IMERG rain, UTC days): parse, units, fills, cache modes |
| `test_services.py` | service functions with in-memory fake sources (e.g. `erosion_risk`, `get_soil_data`) |
| `test_openlandmap.py` | Earth Engine soil adapter: fixtures, cache, error translation (fake sampler, no network) |
| `test_config.py` | `mvp.yaml` validation |
| `fixtures/<source>/` | **real** saved responses, one folder per source |

## Rules
- **No real network** in normal tests. Mock HTTP with `respx`. A test that needs the real API gets
  `@pytest.mark.network` and must still pass offline when deselected.
- **Isolation.** Use the `client` / `make_client` / `env` fixtures. They force `mock` mode, use a temp
  cache dir and ignore the developer's `.env`. Never write to `backend/.cache/` from tests.
- **Fixtures are real responses**, saved once and never hand-edited. To test bad data, load the fixture
  and modify it in the test (see `test_parse_rejects_fill_values`). Name files after what they contain
  (`climatology_alajuela.json`) and note the lat/lon and date in `docs/sources/<source>.md`.
- **One behavior per test.** The name says what it checks: `test_<thing>_<expected behavior>`.
- **Errors** ([`docs/errors.md`](../docs/errors.md)): assert the concrete class (`pytest.raises(SourceDataError,
  match=...)`) or the code (`assert_error(r, 422, ErrorCode.UNKNOWN_CROP)`), never only a status or a message.
- **Assert specifics.** `pytest.raises(X, match="...")` always with `match`. Split `assert a and b`
  into two asserts. Compare floats with `pytest.approx`.
- **Domain tests use inline toy data** with round numbers, not the EcoCrop CSV (its values will change).
- **Parametrize** edge cases instead of copy-pasting tests.
- Keep the fast suite under a few seconds. Mark anything slower `@pytest.mark.slow`.
- Type hints are optional in tests (ruff `ANN` is disabled here).
