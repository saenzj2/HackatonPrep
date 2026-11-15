"""NOAA CPC El Niño indices (RONI official, ONI legacy): adapter, domain labels and the split."""

import json
import logging
from datetime import UTC, date, datetime, timedelta

import httpx
import pytest
import respx

from app.cache import JsonCache
from app.domain.enso import (
    MIN_YEARS_TO_COMPARE,
    EnsoIndex,
    EnsoSeason,
    disagreement_note,
    enso_split,
    label_disagreements,
    latest_estimate_note,
    phase_of,
    season_span,
    year_phase,
)
from app.domain.plan_risk import stress_test
from app.errors import (
    CacheMissError,
    DomainInvariantError,
    SourceDataError,
    SourceUnavailableError,
)
from app.integrations.nasa_power import DAILY_URL
from app.integrations.noaa_enso import MAX_AGE, URLS, NoaaEnso, parse_enso_index
from app.settings import DataMode
from tests.conftest import FIXTURES, load_fixture
from tests.test_plan_risk import Weather, toy_crop

# Real files, fetched 2026-11-15 (Last-Modified 2026-11-03), DJF 1950 → ASO 2026.
RONI_TEXT = (FIXTURES / "noaa_enso" / "RONI_ascii_2026-11-15.txt").read_text(encoding="utf-8")
ONI_TEXT = (FIXTURES / "noaa_enso" / "oni_ascii_2026-11-15.txt").read_text(encoding="utf-8")


# ---------------------------------------------------------------- parsing the real files
def test_parse_real_roni_file():
    roni = parse_enso_index(RONI_TEXT, "RONI")
    assert len(roni.seasons) == 921
    assert roni.seasons[0] == EnsoSeason("DJF", 1950, -1.19)
    assert roni.latest == EnsoSeason("ASO", 2026, 1.97)


def test_parse_real_oni_file_takes_the_anomaly_not_the_sst():
    oni = parse_enso_index(ONI_TEXT, "ONI")  # 4 columns: SEAS YR TOTAL ANOM
    assert oni.seasons[0] == EnsoSeason("DJF", 1950, -1.32)  # TOTAL is 25.01 °C
    assert oni.latest.anomaly_c == pytest.approx(2.46)


@pytest.mark.parametrize(
    ("text", "match"),
    [
        ("", "no 'SEAS YR' header"),
        ("<html>Not found</html>\n", "no 'SEAS YR' header"),
        ("SEAS YR ANOM\nXYZ 1950 0.1\n", "Unexpected NOAA RONI row"),
        ("SEAS YR ANOM\nDJF 1950 abc\n", "Unexpected NOAA RONI row"),
        ("SEAS YR ANOM\nDJF 1950\n", "Unexpected NOAA RONI row"),
        ("SEAS YR ANOM\nDJF 1950 -99.9\n", "impossible value"),
    ],
)
def test_parse_rejects_bad_files(text, match):
    with pytest.raises(SourceDataError, match=match) as exc:
        parse_enso_index(text, "RONI")
    assert exc.value.details["source"] == "noaa_enso"


# ---------------------------------------------------------------- adapter: cache modes
@respx.mock
def test_live_fetches_and_caches_each_index(tmp_path):
    route = respx.get(URLS["RONI"]).mock(return_value=httpx.Response(200, text=RONI_TEXT))
    assert NoaaEnso(JsonCache(tmp_path, DataMode.LIVE)).index("RONI").latest.season == "ASO"
    offline = NoaaEnso(JsonCache(tmp_path, DataMode.CACHED)).index("RONI")
    assert offline.latest.anomaly_c == pytest.approx(1.97)
    assert route.call_count == 1


def _age_cached_copy(cache: JsonCache, index: str, age: timedelta) -> None:
    """Backdate the cache file's fetched_at, as if it had been fetched `age` ago."""
    path = cache.path_for("noaa_enso", {"index": index})
    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["fetched_at"] = (datetime.now(UTC) - age).isoformat()
    path.write_text(json.dumps(entry), encoding="utf-8")


@respx.mock
def test_live_reuses_a_fresh_copy_and_refetches_a_stale_one(tmp_path):
    older = RONI_TEXT.rsplit("ASO", 1)[0]  # the same file one season earlier
    route = respx.get(URLS["RONI"]).mock(
        side_effect=[httpx.Response(200, text=older), httpx.Response(200, text=RONI_TEXT)]
    )
    cache = JsonCache(tmp_path, DataMode.LIVE)
    src = NoaaEnso(cache)
    assert src.index("RONI").latest.season == "JAS"
    assert src.index("RONI").latest.season == "JAS"  # same day: no second request
    assert route.call_count == 1
    _age_cached_copy(cache, "RONI", MAX_AGE + timedelta(minutes=1))
    assert src.index("RONI").latest.season == "ASO"  # stale: new month arrives
    assert route.call_count == 2


def test_cached_mode_serves_a_stale_copy(tmp_path):
    cache = JsonCache(tmp_path, DataMode.LIVE)
    with respx.mock:
        respx.get(URLS["ONI"]).mock(return_value=httpx.Response(200, text=ONI_TEXT))
        NoaaEnso(cache).index("ONI")
    _age_cached_copy(cache, "ONI", timedelta(days=400))
    offline = NoaaEnso(JsonCache(tmp_path, DataMode.CACHED)).index("ONI")
    assert offline.latest.season == "ASO"


@respx.mock
def test_live_falls_back_to_the_cached_copy_when_noaa_fails(tmp_path):
    respx.get(URLS["RONI"]).mock(
        side_effect=[httpx.Response(200, text=RONI_TEXT), httpx.Response(503)]
    )
    src = NoaaEnso(JsonCache(tmp_path, DataMode.LIVE))
    src.index("RONI")
    assert src.index("RONI").latest.anomaly_c == pytest.approx(1.97)


@respx.mock
def test_bad_file_is_never_cached(tmp_path):
    respx.get(URLS["RONI"]).mock(return_value=httpx.Response(200, text="<html>maintenance</html>"))
    cache = JsonCache(tmp_path, DataMode.LIVE)
    with pytest.raises(SourceDataError, match="header"):
        NoaaEnso(cache).index("RONI")
    assert not cache.path_for("noaa_enso", {"index": "RONI"}).exists()


@respx.mock
def test_http_error_without_cache_is_source_unavailable(tmp_path):
    respx.get(URLS["ONI"]).mock(return_value=httpx.Response(500))
    with pytest.raises(SourceUnavailableError, match="HTTP 500") as exc:
        NoaaEnso(JsonCache(tmp_path, DataMode.LIVE)).index("ONI")
    assert exc.value.details == {"source": "noaa_enso", "status": 500}


@respx.mock
def test_network_failure_message_has_no_url(tmp_path):
    respx.get(URLS["RONI"]).mock(side_effect=httpx.ConnectTimeout("timed out"))
    with pytest.raises(SourceUnavailableError, match="ConnectTimeout") as exc:
        NoaaEnso(JsonCache(tmp_path, DataMode.LIVE)).index("RONI")
    assert "http" not in exc.value.message.lower()


def test_cached_mode_miss(tmp_path):
    with pytest.raises(CacheMissError) as exc:
        NoaaEnso(JsonCache(tmp_path, DataMode.CACHED)).index("RONI")
    assert exc.value.details == {"source": "noaa_enso"}


@pytest.mark.network
def test_real_noaa_roni(tmp_path):
    """Calls NOAA. Run with `make test-all`. Not part of CI."""
    roni = NoaaEnso(JsonCache(tmp_path, DataMode.LIVE)).index("RONI")
    assert roni.seasons[0].year == 1950
    assert roni.latest.year >= 2026


# ---------------------------------------------------------------- domain: labels
@pytest.mark.parametrize(
    ("anomaly", "phase"),
    [(0.5, "el_nino"), (0.49, "neutral"), (-0.49, "neutral"), (-0.5, "la_nina")],
)
def test_phase_thresholds(anomaly, phase):
    assert phase_of(anomaly) == phase


def test_sowing_year_uses_the_season_centred_on_the_sowing_month():
    roni = parse_enso_index(RONI_TEXT, "RONI")
    assert roni.anomaly(2020, 11) == pytest.approx(-1.5, abs=0.05)  # OND 2020 (CPC table: -1.5)
    assert year_phase(roni, 2020, 11) == "la_nina"  # Eta/Iota: La Niña
    assert year_phase(roni, 2015, 9) == "el_nino"  # ASO 2015
    assert year_phase(roni, 2030, 1) is None  # not in the index


def test_real_files_disagree_on_a_few_september_sowings():
    roni, oni = parse_enso_index(RONI_TEXT, "RONI"), parse_enso_index(ONI_TEXT, "ONI")
    # Checked by hand 2026-11-15: ASO labels differ in 2016, 2017, 2018, 2024, 2025.
    assert label_disagreements(roni, oni, years=range(2000, 2026), month=9) == 5


def test_disagreement_note_wording():
    note = disagreement_note([(5, 26, 9), (3, 25, 11)])
    assert note.es == (
        "Con el índice anterior de NOAA (ONI), algunos años cambiarían de grupo (El Niño, La "
        "Niña o normal): 5 de 26 en setiembre, 3 de 25 en noviembre"
    )
    assert disagreement_note([(0, 25, 5)]).en.startswith(
        "With NOAA's older index (ONI), no years would change group"
    )


def test_index_must_have_seasons():
    with pytest.raises(DomainInvariantError, match="no seasons"):
        EnsoIndex(name="RONI", seasons=())


# ---------------------------------------------------------------- domain: the split
def index_with(phases: dict[int, float]) -> EnsoIndex:
    """A toy index with the MAM (March-centred) value per year."""
    return EnsoIndex(
        name="RONI",
        seasons=tuple(EnsoSeason("FMA", y, a) for y, a in phases.items()),  # FMA = centred on Mar
    )


def twelve_years_failing(years_failing: set[int]):
    w = Weather(start=date(2001, 1, 1), days=(date(2013, 1, 1) - date(2001, 1, 1)).days)
    for y in years_failing:
        w.set("rain", 0, 19, 0.2, sown=date(y, 3, 1))
    return stress_test(history=w.history(), crop=toy_crop(), sowing_month=3, sowing_day=1)


def test_split_counts_years_and_failures_per_phase():
    plan = twelve_years_failing({2001, 2002, 2006})
    labels = {y: (1.0 if y <= 2004 else -1.0 if y <= 2008 else 0.0) for y in range(2001, 2013)}
    split = enso_split(plan, index_with(labels))
    assert (split.counts["el_nino"].years, split.counts["el_nino"].failed) == (4, 2)
    assert (split.counts["la_nina"].years, split.counts["la_nina"].failed) == (4, 1)
    assert (split.counts["neutral"].years, split.counts["neutral"].failed) == (4, 0)
    assert split.note.en == (
        "This planting would have failed in 2 of 4 El Niño years, 1 of 4 La Niña years and "
        "0 of 4 normal years. Few years, so this may be chance: a pattern in past years, not a "
        "forecast"
    )


def test_split_says_when_a_phase_has_too_few_years():
    plan = twelve_years_failing(set())
    labels = {y: (1.0 if y <= 2003 else 0.0) for y in range(2001, 2013)}  # 3 El Niño, 0 La Niña
    split = enso_split(plan, index_with(labels))
    assert split.counts["el_nino"].years == MIN_YEARS_TO_COMPARE - 1
    assert split.note.en == (
        "Only 3 El Niño years and 0 La Niña years with this sowing date, not enough to compare"
    )
    assert split.note.es.startswith("Solo hubo 3 años de El Niño y 0 años de La Niña")


# ---------------------------------------------------------------- service: NOAA down
@respx.mock
def test_plan_risk_goes_on_without_enso_when_noaa_is_down(make_client, caplog):
    respx.get(DAILY_URL).mock(
        return_value=httpx.Response(
            200, json=load_fixture("nasa_power/daily_history_san_carlos_202009_202011.json")
        )
    )
    for url in URLS.values():
        respx.get(url).mock(return_value=httpx.Response(503))
    body = {"lat": 11.0, "lon": -84.6, "plantings": [{"crop": "beans", "sowing_month": 9}]}
    with caplog.at_level(logging.WARNING):
        r = make_client(data_mode=DataMode.LIVE).post("/plan-risk", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["enso_now"] is None
    assert data["plantings"][0]["enso_split"] is None
    assert any("El Niño data (NOAA) is not available" in g["en"] for g in data["data_gaps"])
    assert "NOAA RONI unavailable" in caplog.text


def test_split_note_uses_the_singular_for_one_year():
    plan = twelve_years_failing(set())
    labels = {y: (1.0 if y == 2001 else -1.0 if y <= 2006 else 0.0) for y in range(2001, 2013)}
    note = enso_split(plan, index_with(labels)).note
    assert note.en.startswith("Only 1 El Niño year with this sowing date")
    assert note.es.startswith("Solo hubo 1 año de El Niño con esta fecha")


def test_latest_estimate_note_names_the_months_not_the_season_code():
    roni = parse_enso_index(RONI_TEXT, "RONI")
    note = latest_estimate_note(roni)
    assert "(Aug–Oct 2026)" in note.en
    assert "(ago–oct 2026)" in note.es
    assert "ASO" not in note.en


@pytest.mark.parametrize(
    ("season", "en"), [("ASO", "Aug–Oct"), ("DJF", "Dec–Feb"), ("NDJ", "Nov–Jan")]
)
def test_season_span_wraps_the_year(season, en):
    assert season_span(season).en == en
