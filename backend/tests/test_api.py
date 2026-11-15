import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import DataMode
from scripts.make_examples import SAN_JOSE_QUERY, seed_san_jose_cache

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


def test_rotation_with_potato_warns_to_check_the_altitude(client):
    body = client.post(
        "/recommendations", json={**CR, "crops": ["potato", "beans"], "top_n": 4}
    ).json()
    for r in body["rotations"]:
        has_potato = any(step["crop_id"] == "potato" for step in r["sequence"])
        warned = any(t["es"].startswith("Papa: revise la altura") for t in r["risks"])
        assert warned == has_potato, r["sequence"]
    # once per rotation, even when potato is in both seasons
    (both,) = [r for r in body["rotations"] if {s["crop_id"] for s in r["sequence"]} == {"potato"}]
    assert sum(t["en"].startswith("Potato:") for t in both["risks"]) == 1


def test_current_rotation_is_the_baseline(client):
    body = client.post(
        # top_n 50 (the max) lists every rotation, whatever the number of MVP crops.
        "/recommendations",
        json={**CR, "current_rotation": ["maize", "maize"], "top_n": 50},
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


def test_permanent_crops_scores_the_mvp_permanent_crops_best_first(client, config):
    r = client.get("/permanent-crops", params={"lat": 10.0, "lon": -84.2})
    assert r.status_code == 200, r.text
    data = r.json()
    assert {c["crop_id"] for c in data["crops"]} == set(config.permanent_crops)
    scores = [c["score"] for c in data["crops"]]
    assert scores == sorted(scores, reverse=True)
    for crop in data["crops"]:
        assert crop["score"] == pytest.approx(min(crop["variable_scores"].values()), abs=1e-4)
    assert data["data_sources"]["crops"] == "ecocrop_perennials"
    assert len(data["year_climate"]["dry_months"]) <= 12


def test_permanent_crops_accepts_a_subset_and_says_altitude_is_not_checked(client):
    r = client.get("/permanent-crops", params={"lat": 10.0, "lon": -84.2, "crops": ["cacao"]})
    data = r.json()
    assert [c["crop_id"] for c in data["crops"]] == ["cacao"]
    assert data["crops"][0]["max_altitude_m"] == 900
    assert any("cacao hasta 900 m" in g["es"] for g in data["data_gaps"])


def test_permanent_crops_are_not_in_the_rotation_catalog(client):
    ids = {c["id"] for c in client.get("/crops").json()["crops"]}
    assert not ids & {"cacao", "coffee", "pineapple", "banana"}


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


# ---------------------------------------------------------------- weather, erosion, soil
# San José: the point of the saved real responses (POWER daily Jan 2026, 5 SRTM points, soil).
SAN_JOSE = {"lat": SAN_JOSE_QUERY["lat"], "lon": SAN_JOSE_QUERY["lon"]}
JAN_2026 = SAN_JOSE_QUERY


@pytest.fixture
def real_client(config, env) -> TestClient:
    """`cached` mode on real saved responses for San José: real values, no network."""
    seed_san_jose_cache(env.cache_dir)
    return TestClient(
        create_app(config=config.model_copy(update={"data_mode": DataMode.CACHED}), env=env)
    )


def test_daily_weather_has_one_row_per_day(client):
    body = client.get("/weather/daily", params=JAN_2026).json()
    assert body["location"] == SAN_JOSE
    assert (body["start"], body["end"]) == ("2026-01-01", "2026-01-31")
    assert [d["date"] for d in body["days"]][:2] == ["2026-01-01", "2026-01-02"]
    assert len(body["days"]) == 31
    assert body["source"] == "mock"


def test_daily_weather_mock_has_no_extremes(client):
    day = client.get("/weather/daily", params=JAN_2026).json()["days"][0]
    assert day["temperature_max_c"] is None
    assert day["temperature_c"] is not None


def test_daily_weather_real_power_values(real_client):
    body = real_client.get("/weather/daily", params=JAN_2026).json()
    assert body["source"] == "nasa_power"
    assert body["days"][0] == {
        "date": "2026-01-01",
        "temperature_c": 22.43,
        "temperature_max_c": 27.06,
        "temperature_min_c": 19.48,
        "rainfall_mm": 1.38,
    }


def test_erosion_levels_match_scores(client):
    body = client.get("/erosion", params=JAN_2026).json()
    words = ["low", "medium", "high"]
    assert body["terrain_erosion_level"] == words[body["terrain_erosion_risk"]]
    assert body["combined_erosion_level"] == words[body["combined_erosion_risk"]]
    assert body["combined_erosion_risk"] >= body["terrain_erosion_risk"]
    assert body["data_sources"] == {"terrain": "mock", "weather": "mock"}


def test_erosion_real_san_jose(real_client):
    body = real_client.get("/erosion", params=JAN_2026).json()
    assert body["data_sources"] == {"terrain": "opentopography", "weather": "nasa_power"}
    assert body["elevation_m"] == 1164
    assert body["slope_pct"] == pytest.approx(2.3)
    assert body["terrain_erosion_level"] == "low"  # flat: under 5 %
    assert body["heavy_rain_days"] == 0  # January is dry season
    assert body["combined_erosion_level"] == "low"


def test_soil_has_three_layers_shallowest_first(client):
    body = client.get("/soil", params=SAN_JOSE).json()
    assert [layer["depth_cm"] for layer in body["layers"]] == [0, 10, 30]
    assert body["source"] == "mock"
    assert body["resolution_m"] == 250


def test_soil_real_openlandmap_values(real_client):
    body = real_client.get("/soil", params=SAN_JOSE).json()
    assert body["source"] == "OpenLandMap"
    assert "CC-BY-SA" in body["attribution"]
    assert body["layers"][0] == {
        "depth_cm": 0,
        "ph": 6.6,
        "organic_carbon_g_kg": 10.0,
        "clay_pct": 38.0,
        "sand_pct": 34.0,
        "silt_pct": 28.0,
        "bulk_density_kg_m3": 1270.0,
        "field_capacity_m3m3": 0.34,
        "texture_class": "clay loam",
    }


@pytest.mark.parametrize("path", ["/weather/daily", "/erosion", "/soil"])
def test_field_data_endpoints_ignore_unknown_query_parameters(client, path):
    """Like every GET endpoint: a cache-busting `_` or a shared `lang` must not fail."""
    r = client.get(path, params={**JAN_2026, "lang": "es", "_": "1731700000"})
    assert r.status_code == 200, r.text
