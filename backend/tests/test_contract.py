"""The running app must match docs/api-contract.yaml (the agreement with the frontend).

If this fails: either update the contract (and tell the frontend), or fix the code.
Compares paths, methods, parameters, request/response refs and every schema in full.
"""

import pytest
import yaml
from openapi_spec_validator import validate

from app.settings import BACKEND_DIR
from tests.conftest import isolated_app

CONTRACT_PATH = BACKEND_DIR / "docs" / "api-contract.yaml"
CONTRACT = yaml.safe_load(CONTRACT_PATH.read_text(encoding="utf-8"))
ACTUAL = isolated_app().openapi()
FASTAPI_BUILTINS = {"HTTPValidationError", "ValidationError"}
METHODS = {"get", "post", "put", "patch", "delete"}


def _ops(spec: dict) -> set[tuple[str, str]]:
    return {(p, m) for p, item in spec["paths"].items() for m in item if m in METHODS}


def _schemas(spec: dict) -> dict:
    return {k: v for k, v in spec["components"]["schemas"].items() if k not in FASTAPI_BUILTINS}


def test_contract_is_valid_openapi():
    validate(CONTRACT)


def test_same_endpoints():
    assert _ops(ACTUAL) == _ops(CONTRACT)


def test_same_schema_names():
    assert set(_schemas(ACTUAL)) == set(_schemas(CONTRACT))


@pytest.mark.parametrize("name", sorted(_schemas(CONTRACT)))
def test_schema_fields_match(name):
    expected = _schemas(CONTRACT)[name]
    actual = _schemas(ACTUAL).get(name)
    assert actual is not None, f"{name} is in the contract but not in the app"
    # Whole schema: field names, required, types, limits (min/max), enums, descriptions.
    assert actual == expected, f"{name} differs from the contract"


@pytest.mark.parametrize(("path", "method"), sorted(_ops(CONTRACT)))
def test_request_and_response_schemas_match(path, method):
    exp, act = CONTRACT["paths"][path][method], ACTUAL["paths"][path][method]
    assert exp.get("requestBody") == act.get("requestBody")
    exp_200 = exp["responses"]["200"]["content"]["application/json"]["schema"]
    act_200 = act["responses"]["200"]["content"]["application/json"]["schema"]
    assert exp_200 == act_200
    exp_params = {(p["name"], p["in"], p.get("required", False)) for p in exp.get("parameters", [])}
    act_params = {(p["name"], p["in"], p.get("required", False)) for p in act.get("parameters", [])}
    assert exp_params == act_params
