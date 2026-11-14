"""Crop traits are 0..1 scores inside the backend and {level, score} in every API response.

The conversion lives in the Trait type (app/api/schemas.py). These tests make sure every response
field holding a trait uses it, so the frontend always gets the word and the number together.
"""

import pytest
from pydantic import ValidationError

from app.api.schemas import Crop, TraitValue
from app.domain.models import TRAIT_FIELDS
from app.errors import DomainInvariantError
from app.services import crop_schema
from tests.conftest import isolated_app
from tests.test_domain import crop

TRAIT_REF = "#/components/schemas/TraitValue"


@pytest.fixture(scope="module")
def schemas() -> dict:
    return isolated_app().openapi()["components"]["schemas"]


def _trait_properties(schemas: dict) -> list[tuple[str, str]]:
    return sorted(
        (schema_name, field)
        for schema_name, schema in schemas.items()
        for field in schema.get("properties", {})
        if field in TRAIT_FIELDS
    )


def _crop_body() -> dict:
    return crop_schema(crop("x")).model_dump()  # test crop: every trait = 0.67


def test_crop_response_has_every_trait(schemas):
    assert {f for s, f in _trait_properties(schemas) if s == "Crop"} == set(TRAIT_FIELDS)


def test_trait_field_in_any_response_is_a_trait_value(schemas):
    """Fails when a new response field (e.g. a badge) declares a trait as a bare number or word."""
    for schema_name, field in _trait_properties(schemas):
        prop = schemas[schema_name]["properties"][field]
        assert prop.get("$ref") == TRAIT_REF, f"{schema_name}.{field}: type it as Trait"


def test_crop_response_has_word_and_score():
    body = _crop_body()
    for field in TRAIT_FIELDS:
        assert body[field] == {"level": "medium", "score": pytest.approx(0.67)}


@pytest.mark.parametrize(
    ("score", "level"), [(0, "none"), (0.33, "low"), (0.5, "medium"), (0.82, "high"), (1, "high")]
)
def test_trait_built_from_score_gets_matching_level(score, level):
    trait = Crop(**{**_crop_body(), "forage_value": score}).forage_value
    assert trait == TraitValue(level=level, score=score)


@pytest.mark.parametrize("value", ["low", True, {"level": "low"}])
def test_trait_rejects_word_or_partial_value(value):
    with pytest.raises(ValidationError, match="forage_value"):
        Crop(**{**_crop_body(), "forage_value": value})


def test_trait_level_must_match_score():
    with pytest.raises(DomainInvariantError, match="doesn't match score"):
        TraitValue(level="high", score=0.1)


def test_trait_score_outside_0_1_is_a_backend_bug():
    with pytest.raises(DomainInvariantError, match="Trait score must be in"):
        Crop(**{**_crop_body(), "forage_value": 1.5})
