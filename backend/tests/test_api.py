import pytest

CR = {"lat": 10.0, "lon": -84.2}


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["data_mode"] == "mock"


def test_crops_lists_mvp_crops(client, config):
    crops = client.get("/crops").json()["crops"]
    assert [c["id"] for c in crops] == config.crops
    assert crops[0]["temperature_c"]["opt_min"] <= crops[0]["temperature_c"]["opt_max"]


def test_conditions(client, config):
    r = client.get("/conditions", params=CR)
    assert r.status_code == 200
    body = r.json()
    assert len(body["monthly"]) == 12
    assert [s["name"] for s in body["seasons"]] == [s.name for s in config.seasons]
    assert body["data_sources"]["climate"] == "mock"


def test_recommendations_default_scope(client, config):
    r = client.post("/recommendations", json=CR)
    assert r.status_code == 200, r.text
    body = r.json()
    rotations = body["rotations"]
    assert 1 <= len(rotations) <= config.top_n
    assert [x["rank"] for x in rotations] == list(range(1, len(rotations) + 1))
    assert rotations == sorted(rotations, key=lambda x: (not x["viable"], -x["score"]))
    assert len(rotations[0]["sequence"]) == len(config.seasons)
    assert rotations[0]["explanation"]
    assert sum(body["priorities"].values()) == 1.0


def test_recommendations_overrides(client):
    r = client.post(
        "/recommendations",
        json={
            **CR,
            "crops": ["beans", "sorghum"],
            "priorities": {"water": 2, "soil": 1, "climate": 1},
            "top_n": 2,
        },
    )
    body = r.json()
    assert r.status_code == 200, r.text
    assert len(body["rotations"]) == 2
    used = {s["crop_id"] for rot in body["rotations"] for s in rot["sequence"]}
    assert used <= {"beans", "sorghum"}
    assert body["priorities"] == {"water": 0.5, "soil": 0.25, "climate": 0.25}


def test_conditions_include_daily_extremes(client):
    body = client.get("/conditions", params=CR).json()
    month = body["monthly"][0]
    assert month["temperature_min_c"] < month["temperature_c"] < month["temperature_max_c"]
    season = body["seasons"][0]
    assert season["temperature_min_c"] < season["temperature_max_c"]


def test_rotations_explain_benefits_risks_gaps_and_evidence(client):
    rot = client.post("/recommendations", json=CR).json()["rotations"][0]
    assert {"heat", "frost"} <= set(rot["sequence"][0]["variable_scores"])
    assert any("mock" in g for g in rot["data_gaps"])
    assert any("mm/month" in e for e in rot["evidence"])
    assert rot["notes"] == rot["benefits"] + rot["risks"]


def test_without_current_rotation_there_is_no_baseline(client):
    body = client.post("/recommendations", json=CR).json()
    assert body["current_rotation"] is None
    assert all(r["score_delta_vs_current"] is None for r in body["rotations"])
    assert not any(r["is_current"] for r in body["rotations"])


def test_current_rotation_is_the_baseline(client):
    body = client.post(
        "/recommendations", json={**CR, "current_rotation": ["maize", "maize"], "top_n": 9}
    ).json()
    current = body["current_rotation"]
    assert [s["crop_id"] for s in current["sequence"]] == ["maize", "maize"]
    assert current["is_current"]
    assert current["score_delta_vs_current"] == 0.0
    (listed,) = [r for r in body["rotations"] if r["is_current"]]
    assert listed["rank"] == current["rank"]
    for r in body["rotations"]:
        assert r["score_delta_vs_current"] == pytest.approx(r["score"] - current["score"], abs=1e-3)


def test_current_rotation_can_rank_below_top_n(client):
    body = client.post(
        "/recommendations", json={**CR, "current_rotation": ["maize", "maize"], "top_n": 1}
    ).json()
    assert len(body["rotations"]) == 1
    assert body["current_rotation"]["rank"] > 1


def test_current_rotation_crops_join_the_candidates(client):
    body = client.post(
        "/recommendations",
        json={**CR, "crops": ["beans", "maize"], "current_rotation": ["sorghum", "sorghum"]},
    ).json()
    assert body["current_rotation"]["sequence"][0]["crop_id"] == "sorghum"


def test_same_input_same_output(client):
    a = client.post("/recommendations", json=CR).json()
    b = client.post("/recommendations", json=CR).json()
    assert a["rotations"] == b["rotations"]


# Error responses are tested in tests/test_errors.py (one place for the error envelope).
