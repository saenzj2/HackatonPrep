"""Plan stress test (app/domain/plan_risk.py) on synthetic daily histories with round numbers.

Toy crop: 100-day cycle, so establishment = days 0–19, flowering = days 45–64, harvest = days
85–99. Baseline weather: 5 mm of rain every day (500 mm per cycle, inside 400–800), 25 °C highs,
wetness 0.6. Each test changes one thing and checks just below / just above a threshold.
"""

import math
from datetime import date, timedelta

import pytest

from app.domain.models import CropProfile, Range
from app.domain.plan_risk import (
    MIN_VALID_SEASONS,
    DailyHistory,
    stages,
    stress_test,
)
from app.errors import DomainInvariantError

SOW = date(2001, 3, 1)


def toy_crop(**overrides) -> CropProfile:
    values = {
        "id": "toy",
        "name": "Toy",
        "name_es": "Juguete",
        "scientific_name": "Toya testa",
        "family": "Poaceae",
        "is_legume": False,
        "cycle_days": 100,
        "temperature_c": Range(10, 18, 28, 30),
        "rainfall_mm": Range(200, 400, 800, 1200),
        "soil_ph": Range(4, 5, 7, 8),
        "root_depth_m": 1.0,
        "is_cover_crop": False,
        "forage_value": 0.5,
        "nutrition_density": 0.5,
        "mycorrhizal_affinity": 0.5,
        "nitrogen_demand": 0.5,
        "market_note": "",
        "sources": ("toy data for tests",),
        "needs_good_drainage": True,
    }
    return CropProfile(**{**values, **overrides})


class Weather:
    """A mutable daily series from `start`, baseline values everywhere, set by sowing-day offset."""

    def __init__(self, start: date = SOW, days: int = 100) -> None:
        self.start = start
        self.rain = [5.0] * days
        self.tmax = [25.0] * days
        self.wet = [0.6] * days
        self.tmin = [15.0] * days

    def set(self, series: str, first: int, last: int, value: float, sown: date = SOW) -> "Weather":
        """Set days first..last (inclusive, counted from `sown`) of rain / tmax / tmin / wet."""
        target = getattr(self, series)
        base = (sown - self.start).days
        for i in range(base + first, base + last + 1):
            target[i] = value
        return self

    def history(self) -> DailyHistory:
        return DailyHistory(
            start=self.start,
            rain_mm=tuple(self.rain),
            tmax_c=tuple(self.tmax),
            tmin_c=tuple(self.tmin),
            root_wetness=tuple(self.wet),
        )


def one_season(w: Weather, crop: CropProfile | None = None):
    result = stress_test(history=w.history(), crop=crop or toy_crop(), sowing_month=3, sowing_day=1)
    assert result.evaluated == 1
    return result.seasons[0]


def finding(w: Weather, cause: str, crop: CropProfile | None = None):
    return next((f for f in one_season(w, crop).findings if f.cause == cause), None)


def test_stage_windows_for_a_100_day_cycle():
    st = stages(toy_crop())  # not in FLOWERING_FRACTIONS: default 45–65 %
    assert (st.establishment.start, st.establishment.stop) == (0, 20)
    assert (st.flowering.start, st.flowering.stop) == (45, 65)
    assert (st.harvest.start, st.harvest.stop) == (85, 100)


@pytest.mark.parametrize(("crop_id", "flowering"), [("rice", (65, 85)), ("beans", (35, 60))])
def test_flowering_window_is_per_crop(crop_id, flowering):
    st = stages(toy_crop(id=crop_id))
    assert (st.flowering.start, st.flowering.stop) == flowering


def test_stage_windows_reject_a_cycle_shorter_than_the_windows():
    with pytest.raises(DomainInvariantError, match="too short"):
        stages(toy_crop(cycle_days=30))


def test_baseline_season_is_ok():
    season = one_season(Weather())
    assert season.outcome == "ok"
    assert season.findings == ()


# ---------------------------------------------------------------- late_dry_start
@pytest.mark.parametrize(
    ("daily_mm", "expected"),
    [
        (1.5, None),  # 30 mm: at the stress threshold, fine
        (1.45, "stress"),  # 29 mm
        (0.5, "stress"),  # 10 mm (and a 20-day dry run): at the fail threshold, still stress
        (0.45, "fail"),  # 9 mm
    ],
)
def test_late_dry_start_rain_thresholds(daily_mm, expected):
    f = finding(Weather().set("rain", 0, 19, daily_mm), "late_dry_start")
    assert (f.severity if f else None) == expected


@pytest.mark.parametrize(("dry_days", "expected"), [(6, None), (7, "stress")])
def test_late_dry_start_dry_run(dry_days, expected):
    f = finding(Weather().set("rain", 0, dry_days - 1, 0.0), "late_dry_start")
    assert (f.severity if f else None) == expected


def test_late_dry_start_text_quotes_both_problems():
    f = finding(Weather().set("rain", 0, 19, 0.45), "late_dry_start")
    assert f.evidence.en == (
        "only 9 mm of rain and 20 days in a row without rain in the first 20 days after sowing"
    )
    assert f.evidence.es == (
        "solo 9 mm de lluvia y 20 días seguidos sin lluvia en los primeros 20 días después "
        "de la siembra"
    )


# ---------------------------------------------------------------- flowering_dry_spell
@pytest.mark.parametrize(
    ("dry_days", "driest_wetness", "expected"),
    [
        (9, 0.3, None),  # too short whatever the soil
        (10, 0.7, None),  # soil still holds water
        (10, 0.69, "stress"),
        (15, 0.6, "stress"),
        (15, 0.59, "fail"),
        (19, 0.9, None),
        (20, 0.9, "fail"),  # long enough to fail whatever the soil
        (10, math.nan, "stress"),  # no wetness data: length alone
        (15, math.nan, "fail"),
    ],
)
def test_flowering_dry_spell_length_and_soil(dry_days, driest_wetness, expected):
    last = 45 + dry_days - 1
    w = Weather().set("rain", 45, last, 0.0).set("wet", 45, last, 0.9)
    if math.isnan(driest_wetness):
        w.set("wet", 45, last, math.nan)  # no wetness data for the whole run
    else:
        w.set("wet", last, last, driest_wetness)  # driest point at the end of the run
    f = finding(w, "flowering_dry_spell")
    assert (f.severity if f else None) == expected


def test_flowering_dry_spell_judges_soil_during_the_run_only():
    w = Weather().set("rain", 45, 59, 0.0).set("wet", 45, 59, 0.8).set("wet", 60, 64, 0.1)
    assert finding(w, "flowering_dry_spell") is None


def test_flowering_dry_spell_text_mentions_dry_soil():
    w = Weather().set("rain", 45, 59, 0.0).set("wet", 45, 59, 0.55)
    f = finding(w, "flowering_dry_spell")
    assert f.evidence.en == (
        "15 days in a row without rain during flowering, and the soil dried to 55% "
        "(100% = soaked; model estimate)"
    )
    assert f.evidence.es == (
        "15 días seguidos sin lluvia durante la floración, y el suelo se secó hasta 55 % "
        "(100 % = empapado; estimación de modelo)"
    )


def test_dry_run_outside_flowering_is_not_a_flowering_dry_spell():
    assert finding(Weather().set("rain", 25, 40, 0.0), "flowering_dry_spell") is None


# ---------------------------------------------------------------- cycle_rain_low
@pytest.mark.parametrize(
    ("daily_mm", "second_half_wetness", "expected"),
    [
        (3.0, 0.3, None),  # 300 mm: below the 400 optimum, but no "below optimum" stress
        (2.0, 0.3, None),  # 200 mm = abs_min
        (1.99, 0.5, "stress"),  # below abs_min, soil still holds water
        (1.99, 0.49, "fail"),  # below abs_min and the root zone dries out
    ],
)
def test_cycle_rain_low_needs_abs_min_and_drying_soil_to_fail(
    daily_mm, second_half_wetness, expected
):
    w = Weather().set("rain", 0, 99, daily_mm).set("wet", 50, 99, second_half_wetness)
    f = finding(w, "cycle_rain_low")
    assert (f.severity if f else None) == expected


def test_too_much_rain_over_the_cycle_is_not_a_cause():
    causes = one_season(Weather().set("rain", 0, 99, 20.0)).causes  # 2,000 mm, abs_max 1,200
    assert "cycle_rain_high" not in causes


def test_cycle_rain_low_text_says_the_crop_used_stored_water():
    f = finding(Weather().set("rain", 0, 99, 1.5), "cycle_rain_low")
    assert f.evidence.en == (
        "only 150 mm of rain over the whole cycle, below the 200 mm usually given for toy "
        "(FAO). The crop would have depended on moisture left in the soil"
    )
    assert f.evidence.es == (
        "solo 150 mm de lluvia en todo el ciclo, menos de los 200 mm que se suelen indicar para "
        "el juguete (FAO). El cultivo habría dependido de la humedad que quedaba en el suelo"
    )


# ---------------------------------------------------------------- harvest_wet
@pytest.mark.parametrize(
    ("window_mm", "expected"),
    [(149.85, None), (150.0, "stress"), (249.9, "stress"), (250.05, "fail")],
)
def test_harvest_wet_thresholds_for_beans(window_mm, expected):
    w = Weather().set("rain", 85, 99, window_mm / 15)
    f = finding(w, "harvest_wet", toy_crop(id="beans"))
    assert (f.severity if f else None) == expected


@pytest.mark.parametrize(
    ("window_mm", "expected"), [(249.9, None), (250.05, "stress"), (450.0, "stress")]
)
def test_harvest_rain_never_fails_grain_crops_like_maize(window_mm, expected):
    w = Weather().set("rain", 85, 99, window_mm / 15)
    f = finding(w, "harvest_wet", toy_crop(id="maize"))
    assert (f.severity if f else None) == expected


def test_wet_soil_alone_is_not_harvest_rain():
    assert finding(Weather().set("wet", 85, 99, 1.0), "harvest_wet", toy_crop(id="beans")) is None


@pytest.mark.parametrize(("needs_drainage", "mentions_soil"), [(True, True), (False, False)])
def test_harvest_wet_adds_soil_evidence_only_for_crops_that_need_drainage(
    needs_drainage, mentions_soil
):
    w = Weather().set("rain", 85, 99, 20.0).set("wet", 85, 99, 0.9)
    crop = toy_crop(id="beans", needs_good_drainage=needs_drainage)
    assert ("soaked" in finding(w, "harvest_wet", crop).evidence.en) is mentions_soil


def test_harvest_wet_text():
    w = Weather().set("rain", 85, 99, 20.0).set("wet", 85, 99, 0.9)
    f = finding(w, "harvest_wet", toy_crop(id="beans"))
    assert f.evidence.en == (
        "300 mm of rain and the soil almost soaked (90%) in the last 15 days before harvest"
    )
    assert f.evidence.es == (
        "300 mm de lluvia y el suelo casi empapado (90 %) en los últimos 15 días antes de la "
        "cosecha"
    )


# ---------------------------------------------------------------- flowering_heat
@pytest.mark.parametrize(
    ("hot_days", "tmax", "expected"),
    [(4, 31.0, None), (5, 31.0, "stress"), (10, 31.0, "fail"), (10, 30.0, None)],  # 30 = abs_max
)
def test_flowering_heat_falls_back_to_abs_max(hot_days, tmax, expected):
    f = finding(Weather().set("tmax", 45, 45 + hot_days - 1, tmax), "flowering_heat")
    assert (f.severity if f else None) == expected


@pytest.mark.parametrize(("tmax", "expected"), [(35.0, None), (35.1, "fail")])
def test_flowering_heat_uses_the_crop_flowering_limit(tmax, expected):
    # Maize: 35 °C at flowering, far below its 47 °C survival limit in EcoCrop.
    crop = toy_crop(id="maize", temperature_c=Range(10, 18, 33, 47))
    f = finding(Weather().set("tmax", 45, 54, tmax), "flowering_heat", crop)
    assert (f.severity if f else None) == expected


def test_hot_days_outside_flowering_dont_count():
    assert finding(Weather().set("tmax", 0, 40, 40.0), "flowering_heat") is None


# ---------------------------------------------------------------- missing data
@pytest.mark.parametrize(("missing", "evaluated"), [(9, 1), (10, 0)])
def test_season_needs_90_percent_of_rain_days(missing, evaluated):
    w = Weather().set("rain", 30, 30 + missing - 1, math.nan)
    result = stress_test(history=w.history(), crop=toy_crop(), sowing_month=3, sowing_day=1)
    assert result.evaluated == evaluated


def test_missing_rain_is_rescaled_not_counted_as_dry():
    # 9 missing days inside flowering: no dry spell, and the cycle total is still 500 mm.
    w = Weather().set("rain", 46, 54, math.nan)
    assert one_season(w).findings == ()


def test_missing_day_breaks_a_dry_run():
    w = Weather().set("rain", 45, 59, 0.0).set("rain", 52, 52, math.nan)  # 7 + gap + 7
    assert finding(w, "flowering_dry_spell") is None


# ---------------------------------------------------------------- calendar mechanics
def test_season_crossing_the_new_year_belongs_to_the_sowing_year():
    w = Weather(start=date(2001, 12, 1), days=100)
    result = stress_test(history=w.history(), crop=toy_crop(), sowing_month=12, sowing_day=1)
    assert [s.year for s in result.seasons] == [2001]


def test_feb_29_sowing_uses_feb_28_in_non_leap_years():
    w = Weather(start=date(2001, 2, 28), days=100)
    result = stress_test(history=w.history(), crop=toy_crop(), sowing_month=2, sowing_day=29)
    assert result.evaluated == 1


def test_unfinished_last_season_is_neither_evaluated_nor_skipped():
    w = Weather(days=99)  # one day short of the harvest
    result = stress_test(history=w.history(), crop=toy_crop(), sowing_month=3, sowing_day=1)
    assert result.evaluated == 0
    assert result.skipped_years == ()


def test_season_with_gaps_is_reported_as_skipped():
    w = Weather().set("rain", 0, 19, math.nan)
    result = stress_test(history=w.history(), crop=toy_crop(), sowing_month=3, sowing_day=1)
    assert result.skipped_years == (2001,)


def test_sowing_before_the_history_starts_is_ignored():
    w = Weather(start=date(2001, 3, 2), days=500)  # 2001-03-01 is one day too early
    result = stress_test(history=w.history(), crop=toy_crop(), sowing_month=3, sowing_day=1)
    assert [s.year for s in result.seasons] == [2002]
    assert result.skipped_years == ()


def test_history_series_must_have_equal_lengths():
    with pytest.raises(DomainInvariantError, match="equally long"):
        DailyHistory(
            start=SOW, rain_mm=(1.0, 2.0), tmax_c=(1.0,), tmin_c=(1.0,), root_wetness=(1.0,)
        )


# ---------------------------------------------------------------- aggregation over years
def years_of_weather(n: int) -> Weather:
    """n seasons sown every Mar 1 from 2001."""
    return Weather(days=(date(2001 + n - 1, 3, 1) - SOW).days + 100)


def sown(year: int) -> date:
    return date(year, 3, 1)


def test_outcome_is_fail_if_any_check_fails():
    w = Weather().set("rain", 0, 19, 1.45).set("tmax", 45, 54, 31.0)  # stress + fail
    assert one_season(w).outcome == "fail"


def test_failure_rate_and_cause_summary_over_years():
    w = years_of_weather(12)
    for year in (2003, 2005):  # fail: very dry start
        w.set("rain", 0, 19, 0.2, sown=sown(year))
    w.set("rain", 0, 19, 1.4, sown=sown(2008))  # stress: 28 mm
    for year in (2004, 2009, 2010):  # harvest rain, stress (toy crop: from 250 mm, never fail)
        w.set("rain", 85, 99, 17.0, sown=sown(year))
    result = stress_test(history=w.history(), crop=toy_crop(), sowing_month=3, sowing_day=1)

    assert result.evaluated == 12
    assert result.failed_years == 2
    assert result.failure_rate == pytest.approx(2 / 12)
    assert not result.not_enough_history
    summaries = result.cause_summaries()
    # Both seen 3 times; the one with a fail comes first.
    assert [c.cause for c in summaries] == ["late_dry_start", "harvest_wet"]
    dry = summaries[0]
    assert dry.years == (2003, 2005, 2008)
    assert dry.severity == "fail"
    assert dry.worst_year == 2003  # 4 mm both years: ties keep the first
    assert summaries[1].severity == "stress"


def test_a_rare_fail_leads_a_frequent_stress():
    w = years_of_weather(5)
    for year in (2001, 2002, 2003, 2004):  # harvest rain stress, 4 years
        w.set("rain", 85, 99, 17.0, sown=sown(year))
    w.set("rain", 0, 19, 0.2, sown=sown(2005))  # one failed start
    result = stress_test(history=w.history(), crop=toy_crop(), sowing_month=3, sowing_day=1)
    assert [c.cause for c in result.cause_summaries()] == ["late_dry_start", "harvest_wet"]


def test_worst_year_is_the_most_extreme_of_the_worst_severity():
    w = years_of_weather(3)
    w.set("rain", 85, 99, 11.0, sown=sown(2001))  # 165 mm, stress
    w.set("rain", 85, 99, 17.0, sown=sown(2002))  # 255 mm, fail
    w.set("rain", 85, 99, 20.0, sown=sown(2003))  # 300 mm, fail
    beans = toy_crop(id="beans")  # harvest rain can fail beans
    result = stress_test(history=w.history(), crop=beans, sowing_month=3, sowing_day=1)
    (summary,) = result.cause_summaries()
    assert summary.worst_year == 2003
    assert summary.worst.evidence.en.startswith("300 mm of rain")


@pytest.mark.parametrize(
    ("seasons", "flagged"), [(MIN_VALID_SEASONS - 1, True), (MIN_VALID_SEASONS, False)]
)
def test_not_enough_history_flag(seasons, flagged):
    w = years_of_weather(seasons)
    result = stress_test(history=w.history(), crop=toy_crop(), sowing_month=3, sowing_day=1)
    assert result.evaluated == seasons
    assert result.not_enough_history is flagged


def test_no_seasons_means_zero_rate_not_a_crash():
    result = stress_test(
        history=Weather(days=50).history(), crop=toy_crop(), sowing_month=3, sowing_day=1
    )
    assert result.failure_rate == 0.0
    assert result.not_enough_history


def test_same_input_same_output():
    w = years_of_weather(5).set("rain", 0, 19, 0.2, sown=sown(2002))
    run = lambda: stress_test(history=w.history(), crop=toy_crop(), sowing_month=3, sowing_day=1)  # noqa: E731
    assert run() == run()


def test_invalid_sowing_date_is_a_bug_upstream():
    with pytest.raises(DomainInvariantError, match="Invalid sowing date"):
        stress_test(history=Weather().history(), crop=toy_crop(), sowing_month=13, sowing_day=1)


def test_history_end_is_inclusive():
    assert Weather(days=3).history().end == SOW + timedelta(days=2)
