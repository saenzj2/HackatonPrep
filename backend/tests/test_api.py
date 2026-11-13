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


def test_same_input_same_output(client):
    a = client.post("/recommendations", json=CR).json()
    b = client.post("/recommendations", json=CR).json()
    assert a["rotations"] == b["rotations"]


# Error responses are tested in tests/test_errors.py (one place for the error envelope).
