"""Layer rules from backend/AGENTS.md, enforced. If this fails, move the code; keep the rule."""

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parent.parent / "app"

# package → modules it must never import
FORBIDDEN = {
    "domain": (
        "app.api",
        "app.integrations",
        "app.services",
        "app.settings",
        "app.cache",
        "app.main",
        "fastapi",
        "pydantic",
        "httpx",
    ),
    "integrations": ("app.api", "app.services", "app.main", "fastapi"),
    "api": ("app.integrations", "app.cache", "httpx"),
}


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


CASES = [(package, path) for package in FORBIDDEN for path in sorted((APP / package).rglob("*.py"))]


@pytest.mark.parametrize(
    ("package", "path"), CASES, ids=[str(p.relative_to(APP)) for _, p in CASES]
)
def test_layer_imports(package: str, path: Path):
    bad = {
        name
        for name in imported_modules(path)
        for forbidden in FORBIDDEN[package]
        if name == forbidden or name.startswith(forbidden + ".")
    }
    assert not bad, f"app/{package} must not import {sorted(bad)} (see backend/AGENTS.md layers)"
