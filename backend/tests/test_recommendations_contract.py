"""POST /recommendations on real NASA POWER data (saved fixture, `cached` mode) meets the contract.

Covers the demo request shapes for #41: every crop in GET /crops as the current crop, no current
rotation at all, and the whole crop catalog. Offline: the fixture is put in a temp cache first.
"""

import pytest

from app.cache import JsonCache
from app.integrations.nasa_power import SOURCE, NasaPowerClimate
from app.settings import DataMode
from tests.conftest import contract_validator, isolated_config, load_fixture

# Representative point of the saved NASA POWER fixture (Alajuela, Costa Rica).
POINT = {"lat": 10.0, "lon": -84.2}
CATALOG = ["rice", "beans", "maize", "sorghum", "cowpea"]  # data/ecocrop_subset.csv
RESPONSE_SCHEMA = contract_validator("RecommendationResponse")


@pytest.fixture
def cached_client(make_client, env):
    """A `cached`-mode client whose cache holds only the real Alajuela climatology."""
    JsonCache(env.cache_dir, DataMode.LIVE).get_or_fetch(
        SOURCE,
        NasaPowerClimate.request_params(POINT["lat"], POINT["lon"]),
        lambda: load_fixture("nasa_power/climatology_alajuela.json"),
    )
    return make_client(data_mode=DataMode.CACHED)


def _recommend(client, **fields) -> dict:
    r = client.post("/recommendations", json={**POINT, **fields})
    assert r.status_code == 200, r.text
    body = r.json()
    assert [e.message for e in RESPONSE_SCHEMA.iter_errors(body)] == []
    return body


def test_response_without_current_rotation_matches_contract(cached_client):
    body = _recommend(cached_client)
    assert body["conditions"]["data_sources"]["climate"] == "nasa_power"
    assert body["location"] == POINT
    assert body["current_rotation"] is None
    assert all(r["score_delta_vs_current"] is None for r in body["rotations"])


def test_listed_crops_are_the_mvp_crops(cached_client, config):
    assert [c["id"] for c in cached_client.get("/crops").json()["crops"]] == config.crops


@pytest.mark.parametrize("crop", isolated_config().crops)
def test_listed_crop_as_current_crop_is_the_baseline(cached_client, config, crop):
    rotation = [crop] * len(config.seasons)
    current = _recommend(cached_client, current_rotation=rotation)["current_rotation"]
    assert [s["crop_id"] for s in current["sequence"]] == rotation
    assert current["score_delta_vs_current"] == pytest.approx(0.0)


def test_whole_crop_catalog_ranks_every_rotation(cached_client, config):
    body = _recommend(cached_client, crops=CATALOG, top_n=50)
    assert len(body["rotations"]) == len(CATALOG) ** len(config.seasons)
    used = {s["crop_id"] for r in body["rotations"] for s in r["sequence"]}
    assert used == set(CATALOG)
