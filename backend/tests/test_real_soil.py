"""Real soil for scoring: NASA SMAP monthly moisture adapter + OpenLandMap pH (MeasuredSoil).

SMAP uses the saved real Earth Engine answers in fixtures/smap/; Earth Engine is never called
(tests pass a fake sampler or only read the cache).
"""

import pytest

from app.cache import JsonCache
from app.domain.models import MonthlySoilWater, SoilConditions, SoilLayer, SoilProfile
from app.errors import CacheMissError, DomainInvariantError, SourceDataError
from app.integrations.measured_soil import MeasuredSoil
from app.integrations.smap import SOURCE, SmapSoilMoisture, parse_monthly_soil_water
from app.settings import DataMode
from tests.conftest import load_fixture

ALAJUELA = load_fixture("smap/monthly_alajuela.json")


def test_parse_real_smap_answer_gives_12_months_of_moisture_and_wetness():
    water = parse_monthly_soil_water(ALAJUELA)
    assert len(water.moisture_m3m3) == 12
    assert len(water.wetness) == 12
    assert water.moisture_m3m3[0] == pytest.approx(0.4487, abs=1e-4)  # January, Alajuela
    assert water.wetness[9] == pytest.approx(0.9473, abs=1e-4)  # October, the wettest
    assert all(0.0 <= w <= 1.0 for w in water.wetness)


@pytest.mark.parametrize(
    ("key", "value", "match"),
    [
        ("m07", None, "no soil moisture"),
        ("m07", 1.5, "outside"),
        ("w07", None, "no soil wetness"),
        ("w07", 1.2, "outside"),
        ("m07", "x", "expected a number"),
    ],
)
def test_parse_rejects_missing_or_bad_month(key, value, match):
    with pytest.raises(SourceDataError, match=match):
        parse_monthly_soil_water({**ALAJUELA, key: value})


def test_live_mode_fetches_once_then_reuses_the_cache(tmp_path):
    calls = []

    def sampler(lat, lon):
        calls.append((lat, lon))
        return ALAJUELA

    src = SmapSoilMoisture(JsonCache(tmp_path, DataMode.LIVE), project_id="p", sampler=sampler)
    assert src.monthly_soil_water(10.001, -84.2) == src.monthly_soil_water(10.0, -84.2)
    assert calls == [(10.0, -84.2)]  # rounded to 2 decimals, fetched once


def test_cached_mode_never_calls_earth_engine(tmp_path):
    src = SmapSoilMoisture(JsonCache(tmp_path, DataMode.CACHED), project_id="p")
    with pytest.raises(CacheMissError, match=SOURCE):
        src.monthly_soil_water(10.0, -84.2)


class FakeProfile:
    name = "openlandmap"

    def __init__(self, *phs):
        self.phs = phs

    def soil_profile(self, lat, lon):
        layers = tuple(
            SoilLayer(
                depth_cm=d,
                ph=ph,
                organic_carbon_g_kg=None,
                clay_pct=None,
                sand_pct=None,
                silt_pct=None,
                bulk_density_kg_m3=None,
                field_capacity_m3m3=None,
                texture_class=None,
            )
            for d, ph in zip((0, 10, 30), self.phs, strict=True)
        )
        return SoilProfile(lat=lat, lon=lon, layers=layers)


class FakeMoisture:
    def monthly_soil_water(self, lat, lon):
        return MonthlySoilWater(
            moisture_m3m3=tuple([0.2] * 6 + [0.4] * 6), wetness=tuple([0.5] * 6 + [0.9] * 6)
        )


def test_measured_soil_uses_root_zone_ph_and_smap_months():
    soil = MeasuredSoil(profile=FakeProfile(5.0, None, 6.0), moisture=FakeMoisture()).soil(10, -84)
    assert soil.ph == pytest.approx(5.5)  # mean of the layers that have a value
    assert soil.moisture_m3m3 == pytest.approx(0.3)
    assert soil.moisture_for((1, 2, 3)) == pytest.approx(0.2)
    assert soil.moisture_for((6, 7)) == pytest.approx(0.3)
    assert soil.wetness_for((7, 8)) == pytest.approx(0.9)


def test_measured_soil_without_any_ph_is_an_error_not_a_guess():
    with pytest.raises(SourceDataError, match="no soil pH"):
        MeasuredSoil(profile=FakeProfile(None, None, None), moisture=FakeMoisture()).soil(10, -84)


def test_soil_conditions_needs_12_monthly_values():
    with pytest.raises(DomainInvariantError, match="12 monthly"):
        SoilConditions(ph=6, moisture_m3m3=0.3, moisture_monthly_m3m3=(0.3,) * 11)
