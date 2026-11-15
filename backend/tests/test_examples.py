"""The example responses in docs/examples/ (the frontend's mock data) must match the contract.

If this fails after a contract change, regenerate them:
    cd backend && .venv/bin/python -m scripts.make_examples
"""

import json

import pytest

from app.settings import BACKEND_DIR
from scripts.make_examples import build_examples, render
from tests.conftest import contract_validator

EXAMPLES_DIR = BACKEND_DIR / "docs" / "examples"

# example file → contract schema it must satisfy
EXAMPLES = {
    "conditions_alajuela.json": "Conditions",
    "recommendation_request_alajuela.json": "RecommendationRequest",
    "recommendation_alajuela.json": "RecommendationResponse",
    "crops.json": "CropsResponse",
    "permanent_crops_alajuela.json": "PermanentCropsResponse",
    "weather_daily_san_jose.json": "DailyWeatherResponse",
    "erosion_san_jose.json": "ErosionRiskResponse",
    "soil_san_jose.json": "SoilProfileResponse",
}


def test_every_example_file_is_checked():
    assert {p.name for p in EXAMPLES_DIR.glob("*.json")} == set(EXAMPLES)


@pytest.mark.parametrize(("file_name", "schema_name"), sorted(EXAMPLES.items()))
def test_example_matches_contract(file_name, schema_name):
    body = json.loads((EXAMPLES_DIR / file_name).read_text(encoding="utf-8"))
    errors = [e.message for e in contract_validator(schema_name).iter_errors(body)]
    assert errors == []


def test_recommendation_example_includes_current_rotation():
    body = json.loads((EXAMPLES_DIR / "recommendation_alajuela.json").read_text(encoding="utf-8"))
    assert body["current_rotation"]["is_current"] is True
    assert len(body["rotations"]) >= 3


def test_examples_match_what_the_app_produces_now():
    """Catches stale mock data after scoring, config or schema changes."""
    for name, body in build_examples().items():
        committed = (EXAMPLES_DIR / name).read_text(encoding="utf-8")
        assert committed == render(body), f"{name} is stale; run python -m scripts.make_examples"
