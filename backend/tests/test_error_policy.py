"""Enforces docs/errors.md. If a test here fails, follow the guide; don't loosen the test.

Static checks over app/ source + consistency between the catalog, the HTTP mapping,
the guide, the API contract and the HTTP tests.
"""

from __future__ import annotations

import ast
import inspect
import re
from pathlib import Path

import pytest
import yaml

import app.errors as catalog
from app.api.errors import STATUS_BY_CODE
from app.errors import ABSTRACT_ERRORS, AppError, ErrorCode
from app.settings import BACKEND_DIR
from tests.conftest import isolated_app

APP_DIR = BACKEND_DIR / "app"
CATALOG_FILE = APP_DIR / "errors.py"
HTTP_ERRORS_FILE = APP_DIR / "api" / "errors.py"
GUIDE = BACKEND_DIR / "docs" / "errors.md"
CONTRACT = BACKEND_DIR / "docs" / "api-contract.yaml"
HTTP_TESTS = BACKEND_DIR / "tests" / "test_errors.py"

# Codes produced by the HTTP layer itself rather than by an AppError subclass.
HANDLER_CODES = {
    ErrorCode.VALIDATION_FAILED,
    ErrorCode.NOT_FOUND,
    ErrorCode.METHOD_NOT_ALLOWED,
    ErrorCode.HTTP_ERROR,
    ErrorCode.INTERNAL_ERROR,
}
# Codes that can't be triggered through a normal request (startup-only or framework-generic).
NOT_REACHABLE_BY_REQUEST = {ErrorCode.CONFIG_INVALID, ErrorCode.HTTP_ERROR}
PYDANTIC_VALIDATORS = {"field_validator", "model_validator"}

CONCRETE_ERRORS = {
    name: cls
    for name, cls in inspect.getmembers(catalog, inspect.isclass)
    if issubclass(cls, AppError) and cls not in ABSTRACT_ERRORS
}
SOURCES = sorted(APP_DIR.rglob("*.py"))


def _ids(path: Path) -> str:
    return str(path.relative_to(APP_DIR))


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _name(node: ast.expr | None) -> str | None:
    if isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _decorator_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    return {n for d in fn.decorator_list if (n := _name(d))}


def _raises_with_context(tree: ast.Module) -> list[tuple[ast.Raise, set[str]]]:
    """Every raise statement with the decorator names of its enclosing functions."""
    found: list[tuple[ast.Raise, set[str]]] = []

    def visit(node: ast.AST, decorators: set[str]) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                visit(child, decorators | _decorator_names(child))
            elif isinstance(child, ast.Raise):
                found.append((child, decorators))
                visit(child, decorators)
            else:
                visit(child, decorators)

    visit(tree, set())
    return found


# ---------------------------------------------------------------- where errors live
@pytest.mark.parametrize("path", [p for p in SOURCES if p != CATALOG_FILE], ids=_ids)
def test_exception_classes_only_defined_in_catalog(path: Path):
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.ClassDef):
            bases = {_name(b) or "" for b in node.bases}
            bad = {b for b in bases if b.endswith(("Error", "Exception")) or b in CONCRETE_ERRORS}
            assert not bad, (
                f"{path.name}:{node.lineno} defines exception {node.name}. "
                "Add it to app/errors.py instead (docs/errors.md › Adding an error)."
            )


@pytest.mark.parametrize("path", SOURCES, ids=_ids)
def test_only_catalog_errors_are_raised(path: Path):
    for node, decorators in _raises_with_context(_tree(path)):
        if node.exc is None:  # bare `raise` re-raises inside an except block: fine
            continue
        raised = _name(node.exc)
        if raised == "ValueError" and decorators & PYDANTIC_VALIDATORS:
            continue  # Pydantic validators must raise ValueError; Pydantic converts it
        assert raised in CONCRETE_ERRORS, (
            f"{path.name}:{node.lineno} raises {raised}. Raise a concrete class from "
            f"app/errors.py: {sorted(CONCRETE_ERRORS)}"
        )


@pytest.mark.parametrize("path", [p for p in SOURCES if p != HTTP_ERRORS_FILE], ids=_ids)
def test_error_responses_only_built_in_api_errors(path: Path):
    """Nobody else may build error responses or raise HTTPException."""
    forbidden = {"HTTPException", "JSONResponse", "RequestValidationError"}
    for node in ast.walk(_tree(path)):
        if isinstance(node, ast.ImportFrom):
            bad = forbidden & {a.name for a in node.names}
            assert not bad, f"{path.name}:{node.lineno} imports {bad}. Raise an AppError instead."


# ---------------------------------------------------------------- catalog integrity
def test_every_concrete_error_has_a_unique_code():
    codes = [cls.code for cls in CONCRETE_ERRORS.values()]
    assert all(isinstance(c, ErrorCode) for c in codes)
    assert len(codes) == len(set(codes)), "Two error classes share a code"


def test_every_code_is_produced_by_something():
    produced = {cls.code for cls in CONCRETE_ERRORS.values()} | HANDLER_CODES
    assert produced == set(ErrorCode), f"Unused codes: {set(ErrorCode) - produced}"


def test_every_code_has_an_http_status():
    assert set(STATUS_BY_CODE) == set(ErrorCode)


# ---------------------------------------------------------------- guide, contract, tests agree
def test_every_code_is_documented_in_the_guide():
    guide = GUIDE.read_text(encoding="utf-8")
    # Rows of the "Error codes" table: | `code` | <HTTP status> | ...
    table_codes = set(re.findall(r"^\|\s*`([a-z_]+)`\s*\|\s*\d", guide, flags=re.MULTILINE))
    assert table_codes == {c.value for c in ErrorCode}, (
        "docs/errors.md code table out of sync. "
        f"Missing: {sorted({c.value for c in ErrorCode} - table_codes)}, "
        f"unknown: {sorted(table_codes - {c.value for c in ErrorCode})}"
    )


def test_contract_lists_every_code():
    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    enum = set(contract["components"]["schemas"]["ErrorCode"]["enum"])
    assert enum == {c.value for c in ErrorCode}


def test_every_request_reachable_code_has_an_http_test():
    text = HTTP_TESTS.read_text(encoding="utf-8")
    missing = {
        c for c in set(ErrorCode) - NOT_REACHABLE_BY_REQUEST if f"ErrorCode.{c.name}" not in text
    }
    assert not missing, f"Add a case to tests/test_errors.py for: {sorted(missing)}"


def test_every_route_documents_its_errors():
    spec = isolated_app().openapi()
    ref = "#/components/schemas/ErrorResponse"
    for path, item in spec["paths"].items():
        for method, op in item.items():
            responses = op["responses"]
            where = f"{method.upper()} {path}"
            assert "500" in responses, f"{where}: add responses=error_responses(...)"
            for status, resp in responses.items():
                if status.startswith(("4", "5")):
                    schema = resp["content"]["application/json"]["schema"]
                    assert schema == {"$ref": ref}, f"{where} {status} must use ErrorResponse"
            if op.get("parameters") or op.get("requestBody"):
                assert "422" in responses, f"{where} takes input, so it must declare 422"
