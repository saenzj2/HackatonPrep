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
    assert any("simulated" in g["en"] for g in rot["data_gaps"])
    assert any("simulados" in g["es"] for g in rot["data_gaps"])
    assert any("mm of rain per month" in e["en"] for e in rot["evidence"])
    assert rot["notes"] == rot["benefits"] + rot["risks"]


@pytest.mark.parametrize("current", [None, ["maize", "beans"], ["rice", "rice"]])
def test_every_strategy_carries_all_five_explanation_parts(client, current):
    """#29: why (explanation), evidence, benefits, information gaps, risks for local review."""
    body = client.post("/recommendations", json={**CR, "top_n": 9, "current_rotation": current})
    strategies = body.json()["rotations"]
    if current:
        strategies.append(body.json()["current_rotation"])
    for rot in strategies:
        ids = [step["crop_id"] for step in rot["sequence"]]
        assert rot["explanation"], ids
        for part in ("evidence", "benefits", "data_gaps", "risks"):
            assert rot[part], f"{part} empty for {ids}"
        assert any(r["en"].startswith("Local review") for r in rot["risks"]), ids
        assert any(r["es"].startswith("Revisión local") for r in rot["risks"]), ids


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


def test_recommendation_is_for_the_requested_point(client):
    # The API takes one representative point (e.g. picked inside a selected area) and echoes it
    # unchanged: no snapping, no area or polygon average.
    point = {"lat": 10.37, "lon": -84.47}
    body = client.post("/recommendations", json=point).json()
    assert body["location"] == point
    assert body["conditions"]["location"] == point


def test_same_input_same_output(client):
    a = client.post("/recommendations", json=CR).json()
    b = client.post("/recommendations", json=CR).json()
    assert a["rotations"] == b["rotations"]


# Error responses are tested in tests/test_errors.py (one place for the error envelope).


def test_planting_windows_for_mvp_crops(client, config):
    body = client.get("/planting-windows", params=CR).json()
    assert [c["crop_id"] for c in body["crops"]] == config.crops
    first = body["crops"][0]
    assert [m["sowing_month"] for m in first["sowing_months"]] == list(range(1, 13))
    assert first["sowing_months"][10]["months_in_field"][:2] == [11, 12]  # sown in Nov, wraps
    assert body["data_sources"]["climate"] == "mock"


def test_planting_windows_only_requested_crops(client):
    body = client.get("/planting-windows", params={**CR, "crops": ["maize", "beans"]}).json()
    assert [c["crop_id"] for c in body["crops"]] == ["maize", "beans"]


def test_planting_window_months_are_good_sowing_months(client):
    crop = client.get("/planting-windows", params={**CR, "crops": ["maize"]}).json()["crops"][0]
    good = {m["sowing_month"] for m in crop["sowing_months"] if m["is_good"]}
    for w in crop["windows"]:
        assert {w["first_month"], w["last_month"], w["best_month"]} <= good


def test_limiting_factor_is_the_weakest_variable_or_none_when_ideal(client):
    body = client.get("/planting-windows", params=CR).json()
    months = [m for c in body["crops"] for m in c["sowing_months"]]
    for m in months:
        weakest = min(m["variable_scores"], key=m["variable_scores"].get)
        if m["variable_scores"][weakest] < 1:
            assert m["limiting_factor"] == weakest
        else:
            assert m["limiting_factor"] is None
    assert any(m["limiting_factor"] for m in months)  # the check above ran on real cases


def test_conditions_include_monthly_soil_moisture(client):
    soil = client.get("/conditions", params=CR).json()["soil"]
    assert len(soil["moisture_monthly_m3m3"]) == 12
    assert soil["moisture_m3m3"] == pytest.approx(sum(soil["moisture_monthly_m3m3"]) / 12, abs=1e-3)


def _texts(node):
    """Every {en, es} object anywhere in a response."""
    if isinstance(node, dict):
        if set(node) == {"en", "es"}:
            yield node
        else:
            for v in node.values():
                yield from _texts(v)
    elif isinstance(node, list):
        for v in node:
            yield from _texts(v)


def test_every_farmer_text_comes_in_english_and_spanish(client):
    rec = client.post(
        "/recommendations", json={**CR, "current_rotation": ["maize", "maize"]}
    ).json()
    windows = client.get("/planting-windows", params=CR).json()
    texts = list(_texts(rec)) + list(_texts(windows))
    assert len(texts) > 20
    for t in texts:
        assert t["en"].strip()
        assert t["es"].strip()
        assert t["es"] != t["en"], t  # really translated, not copied


def test_spanish_texts_read_right(client):
    """Exact Spanish sentences: decimal comma, `%`/`°C` spacing, 'setiembre' for September."""
    rec = client.post(
        "/recommendations", json={**CR, "current_rotation": ["maize", "maize"]}
    ).json()
    windows = client.get("/planting-windows", params=CR).json()
    es = {t["es"] for t in list(_texts(rec)) + list(_texts(windows))}
    assert (
        "Maíz (primera) → Frijol (postrera): cambiar de familia corta plagas, la leguminosa "
        "aporta un poco de nitrógeno. Puntaje 1,00 de 1."
    ) in es
    assert (
        "Frijol en primera: calor fuerte, la máxima promedio (32,6 °C) supera lo que aguanta "
        "el cultivo (32 °C)"
    ) in es
    assert (
        "Muy seco para establecer maíz sembrado en febrero: febrero suele tener solo 18 mm de "
        "lluvia, y el maíz necesita unos 100 mm al mes para establecerse y crecer (mínimo 80)"
    ) in es


PLAN = {
    "lat": 11.0,
    "lon": -84.6,
    "plantings": [{"crop": "maize", "sowing_month": 5, "sowing_day": 15}],
}


def test_plan_risk_returns_one_result_per_planting(client):
    body = {**PLAN, "plantings": [*PLAN["plantings"], {"crop": "beans", "sowing_month": 9}]}
    r = client.post("/plan-risk", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert [p["crop_id"] for p in data["plantings"]] == ["maize", "beans"]
    assert data["plantings"][0]["sowing_date"] == "05-15"
    assert data["plantings"][1]["sowing_date"] == "09-01"  # day defaults to 1


def test_plan_risk_texts_come_in_english_and_spanish(client):
    data = client.post("/plan-risk", json=PLAN).json()
    texts = list(_texts(data))
    assert len(texts) > 5
    for t in texts:
        assert t["en"].strip()
        assert t["es"].strip()
        assert t["es"] != t["en"], t


def test_plan_risk_harvest_is_sowing_plus_the_crop_cycle(client):
    body = {**PLAN, "plantings": [{"crop": "beans", "sowing_month": 9, "sowing_day": 1}]}
    planting = client.post("/plan-risk", json=body).json()["plantings"][0]
    assert planting["harvest_date"] == "11-30"  # beans: 90-day cycle


def test_plan_risk_counts_agree_with_the_years(client):
    data = client.post("/plan-risk", json=PLAN).json()
    planting = data["plantings"][0]
    outcomes = [y["outcome"] for y in planting["years"]]
    assert len(outcomes) == data["years_evaluated"]["count"]
    assert outcomes.count("fail") == planting["failed_years"]
    assert planting["failure_rate"] == pytest.approx(
        planting["failed_years"] / len(outcomes), abs=1e-3
    )
    for cause in planting["causes"]:
        assert cause["count"] == len(cause["years"])
        assert all(
            cause["cause"] in y["causes"] for y in planting["years"] if y["year"] in cause["years"]
        )


def test_plan_risk_alternatives_fail_less_than_the_plan(client):
    # A dry-season sowing in the mock climate fails often, so better options exist.
    body = {**PLAN, "plantings": [{"crop": "beans", "sowing_month": 1, "sowing_day": 15}]}
    planting = client.post("/plan-risk", json=body).json()["plantings"][0]
    assert planting["failed_years"] > 0
    assert planting["alternatives"]
    for alt in planting["alternatives"]:
        assert alt["failure_rate"] < planting["failure_rate"]


def test_plan_risk_reports_its_sources_and_gaps(client):
    data = client.post("/plan-risk", json=PLAN).json()
    assert data["data_sources"] == ["mock"]  # tests run in mock mode
    assert data["enso_now"]["season"] == "ASO 2026"  # the mock index ends there
    gaps = " ".join(g["en"] for g in data["data_gaps"])
    assert "not measured on your farm" in gaps
    assert "assumes no irrigation" in gaps
    assert "A 'failed' year means" in gaps  # defines the word once for the farmer


def test_plan_risk_labels_years_and_splits_failures_by_enso_phase(client):
    data = client.post("/plan-risk", json=PLAN).json()
    planting = data["plantings"][0]
    assert all(y["enso"] in ("el_nino", "la_nina", "neutral") for y in planting["years"])
    split = planting["enso_split"]
    phases = ("el_nino", "la_nina", "neutral")
    assert sum(split[p]["years"] for p in phases) == len(planting["years"])
    assert sum(split[p]["failed"] for p in phases) == planting["failed_years"]
    for p in phases:  # each phase's count matches the per-year labels
        assert split[p]["years"] == sum(y["enso"] == p for y in planting["years"])
    assert split["note"]["en"]
    assert split["note"]["es"]


def test_plan_risk_enso_now_is_the_latest_season(client):
    now = client.post("/plan-risk", json=PLAN).json()["enso_now"]
    assert now["phase"] in ("el_nino", "la_nina", "neutral")
    assert now["source"].startswith("NOAA CPC RONI")
