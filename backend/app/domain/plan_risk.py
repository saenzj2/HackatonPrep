"""Plan stress test: replay one planting (crop + sowing date) against every past year of weather.

For each sowing year the crop's cycle is laid over that year's real days, cut into stages
(establishment, flowering, harvest), and a few simple checks say whether the season would have
been fine (`ok`), hurt the crop (`stress`) or failed (`fail`). Each check is one sentence a farmer
can follow: "only 8 mm of rain in the first 20 days after sowing".

Pure: no I/O, stdlib only (the service turns the adapter's DataFrame into a `DailyHistory`).
Every threshold below is a PLACEHOLDER pending the agro-logic review (docs/decisions.md).
No crop growth model and no yields: these are weather patterns known to hurt crops.
"""

from __future__ import annotations

import calendar
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Literal

from app.domain.indicators import DRY_DAY_MM
from app.domain.models import CropProfile
from app.domain.text import Text, num, pct
from app.errors import DomainInvariantError

Cause = Literal[
    "late_dry_start",
    "flowering_dry_spell",
    "cycle_rain_low",
    "harvest_wet",
    "flowering_heat",
]
# `cycle_rain_high` stays in the API enum but is never produced (agro-logic review 2026-11-15:
# EcoCrop's rainfall ranges are annual, and excess rain does its damage through the harvest and
# waterlogging pathways, not the cycle total).
Severity = Literal["stress", "fail"]
Outcome = Literal["ok", "stress", "fail"]

# --- Stage windows. Placeholders, agro-logic review 2026-11-15. ------------------------------
ESTABLISHMENT_DAYS = 20  # days 0..19 after sowing: germination and early growth
HARVEST_WINDOW_DAYS = 15  # the last 15 days before harvest: drying down in the field
# Flowering as fractions of cycle_days, per crop id. Agro-logic review, fact-checked 2026-11-15:
# - maize 45–65 %: lowland tropical maize flowers at 55–60 of ~115 days (IITA maize guide); FAO's
#   critical window runs ~2 weeks before to 2–3 weeks after silking;
# - beans 35–60 %: R6 flowering ~day 32–40 of 85–90 (Fernández, Gepts & López 1986, CIAT);
#   Costa Rican bean Nambí flowers at 32–33 days;
# - cowpea: same window as beans (plausible, no separate source found);
# - rice 65–85 %: booting to anthesis; ripening ~30 days after heading, so a 120-day rice heads
#   ~day 90 (IRRI growth phases, via the Rice Knowledge Bank);
# - sorghum 50–70 %: half-bloom at 60–69 days for medium hybrids (K-State MF3234).
FLOWERING_FRACTIONS: dict[str, tuple[float, float]] = {
    "maize": (0.45, 0.65),
    "beans": (0.35, 0.60),
    "cowpea": (0.35, 0.60),
    "rice": (0.65, 0.85),
    "sorghum": (0.50, 0.70),
}
DEFAULT_FLOWERING_FRACTIONS = (0.45, 0.65)  # crops not listed above

# --- Season validity. ------------------------------------------------------------------------
# A season counts only if all its days are in the history and less than this share of its rain
# days are missing (window totals are rescaled from the days present). Placeholder.
MAX_MISSING_RAIN_FRACTION = 0.10
# Under this many valid seasons the result is flagged not_enough_history (a 200 with a data gap,
# decisions.md 2026-11-15). Placeholder.
MIN_VALID_SEASONS = 10

# --- Checks. Placeholders, agro-logic review 2026-11-15. -------------------------------------
# A day with < DRY_DAY_MM (1 mm, ETCCDI wet-day threshold, from indicators.py) is dry.
# late_dry_start: little rain to establish the crop, or a dry run right after sowing. Inspired by
# onset / false-start rules, not the same rule: Sivakumar 1988 (Sahel) starts the season after
# ≥ 20 mm in 3 days with no dry spell > 7 days in the next 30 days.
ESTABLISHMENT_RAIN_STRESS_MM = 30.0
ESTABLISHMENT_RAIN_FAIL_MM = 10.0
ESTABLISHMENT_DRY_RUN_DAYS = 7
# flowering_dry_spell: longest run of dry days inside flowering, the most yield-sensitive stage
# (FAO crop information, maize). The soil is judged at its driest point DURING the run (minimum
# MERRA-2 GWETROOT, 0..1): a full root zone carries a crop roughly 1–2 weeks, depending on the
# soil (FAO-56 Table 22: beans p ≈ 0.45, roots 0.6–0.9 m; at ~4 mm/day). Agro-logic review:
# - stress: run ≥ 10 days and the soil got below 0.7;
# - fail: run ≥ 15 days and the soil got below 0.6, or run ≥ 20 days whatever the soil.
# Without wetness data for the run, length alone decides (10 stress, 15 fail).
FLOWERING_DRY_STRESS_DAYS = 10
FLOWERING_DRY_FAIL_DAYS = 15
FLOWERING_DRY_ALWAYS_FAIL_DAYS = 20
FLOWERING_DRY_STRESS_WETNESS = 0.7
FLOWERING_DRY_FAIL_WETNESS = 0.6
# cycle_rain_low: cycle rain below the crop's EcoCrop rainfall_mm.abs_min. No "below optimum"
# stress: EcoCrop ranges are annual figures, and a crop sown at the end of the rains grows on
# water stored in the soil. A fail only if the root zone also dries in the second half of the
# cycle (mean GWETROOT below this); otherwise stress. Agro-logic review 2026-11-15.
CYCLE_LOW_SOIL_WETNESS = 0.5
# harvest_wet: rain in the harvest window (pods rot and sprout, web blight, grain can't dry).
# Beans and cowpea: stress 150 mm, fail 250 mm. Maize, rice, sorghum: stress from 250 mm, never a
# fail: maize gets "la dobla" (the stalk bent below the ear so it sheds rain; Munguía 1995), and
# "never fails" is a modelling choice, not a sourced value. Agro-logic review 2026-11-15.
# (stress mm, fail mm or None), per crop id.
HARVEST_RAIN_MM: dict[str, tuple[float, float | None]] = {
    "beans": (150.0, 250.0),
    "cowpea": (150.0, 250.0),
    "maize": (250.0, None),
    "rice": (250.0, None),
    "sorghum": (250.0, None),
}
DEFAULT_HARVEST_RAIN_MM: tuple[float, float | None] = (250.0, None)  # crops not listed above
# Soil wetness is only extra evidence when the rain clause fires, for crops that need good
# drainage: a ~50 km model value is near saturation for weeks in wet zones and can't see a field's
# drainage, so it never triggers a finding alone (same spirit as suitability's waterlogging rule).
HARVEST_SOIL_WETNESS = 0.85
# flowering_heat: days in flowering above the crop's flowering heat limit (°C). Pollen and seed
# set fail well below the survival limit (EcoCrop temperature_c.abs_max, still used for crops not
# listed). Agro-logic review 2026-11-15:
# - beans 32 °C: Porch & Jahn 2001 found abnormal pollen at 32/27 °C day/night before anthesis.
#   30 °C flagged ordinary Sep sowings at Los Chiles in 7 of 26 years (decisions.md). Hot NIGHTS
#   (> 20 °C) are the main driver for beans and cowpea (Cruz et al. 2023, Front. Plant Sci.
#   14:1145858) and are not checked yet (calibration pending, decisions.md 2026-11-15);
# - maize 35 °C: pollen viability falls above 35 °C (Hatfield & Prueger 2015);
# - rice 35 °C air: sterility from ~33.7 °C panicle tissue temperature (Jagadish et al. 2007);
#   reviews give 35–38.5 °C air;
# - cowpea 35 °C: no source for a day threshold (night heat drives pod-set loss: Hall's group);
# - sorghum 36 °C: ≥ 36/26 °C cut pollen viability and seed set vs 32/22 °C (Prasad et al. 2006,
#   Agric. For. Meteorol. 139:237-251). Was 38 °C before the fact-check.
FLOWERING_HEAT_LIMIT_C: dict[str, float] = {
    "beans": 32.0,
    "maize": 35.0,
    "rice": 35.0,
    "cowpea": 35.0,
    "sorghum": 36.0,
}
FLOWERING_HEAT_STRESS_DAYS = 5
FLOWERING_HEAT_FAIL_DAYS = 10
# Warm nights at flowering (beans, cowpea): nights above 20 °C reduce pod set and are the main
# heat driver for these crops (Cruz et al. 2023, Front. Plant Sci. 14:1145858; Hall's group for
# cowpea). NOT a yearly check: at Los Chiles every flowering season has them (calibrated on MERRA-2
# Tmin, decisions.md 2026-11-15), so it is a property of the place. A note is shown when a typical
# season has at least WARM_NIGHT_NOTE_NIGHTS of them. Placeholder count.
WARM_NIGHT_C = 20.0
WARM_NIGHT_CROPS = frozenset({"beans", "cowpea"})
WARM_NIGHT_NOTE_NIGHTS = 5

_SEVERITY_RANK = {"stress": 1, "fail": 2}


@dataclass(frozen=True)
class DailyHistory:
    """Consecutive daily weather at one point. NaN = no data that day.

    rain_mm: daily rain (mm, GPM IMERG). tmax_c / tmin_c: daily max / min at 2 m (°C).
    root_wetness: root-zone soil wetness, 0 dry .. 1 saturated (MERRA-2 GWETROOT).
    """

    start: date
    rain_mm: tuple[float, ...]
    tmax_c: tuple[float, ...]
    tmin_c: tuple[float, ...]
    root_wetness: tuple[float, ...]

    def __post_init__(self) -> None:
        n = len(self.rain_mm)
        if not n or any(len(s) != n for s in (self.tmax_c, self.tmin_c, self.root_wetness)):
            raise DomainInvariantError("DailyHistory series must be non-empty and equally long")

    @property
    def end(self) -> date:
        """Last day in the history (inclusive)."""
        return self.start + timedelta(days=len(self.rain_mm) - 1)

    def offset(self, day: date) -> int:
        return (day - self.start).days


@dataclass(frozen=True)
class Finding:
    """One check that went wrong in one season, with that year's numbers as farmer text."""

    cause: Cause
    severity: Severity
    # How bad it was, comparable across years of the same cause (higher = worse). Picks the
    # worst year to quote in the explanation.
    badness: float
    evidence: Text  # "only 8 mm of rain in the first 20 days after sowing" (no year)


@dataclass(frozen=True)
class SeasonResult:
    year: int  # sowing year
    findings: tuple[Finding, ...]
    cycle_rain_mm: float | None = None  # rain over the whole cycle (None if no rain data)
    warm_flowering_nights: int | None = None  # nights > WARM_NIGHT_C in flowering (None: no data)

    @property
    def outcome(self) -> Outcome:
        if any(f.severity == "fail" for f in self.findings):
            return "fail"
        return "stress" if self.findings else "ok"

    @property
    def causes(self) -> tuple[Cause, ...]:
        return tuple(f.cause for f in self.findings)


@dataclass(frozen=True)
class CauseSummary:
    cause: Cause
    severity: Severity  # worst seen
    years: tuple[int, ...]
    worst_year: int
    worst: Finding


@dataclass(frozen=True)
class PlanRiskResult:
    crop_id: str
    sowing_month: int
    sowing_day: int
    seasons: tuple[SeasonResult, ...]  # valid seasons only, oldest first
    skipped_years: tuple[int, ...]  # sowing years in range but with missing data

    @property
    def evaluated(self) -> int:
        return len(self.seasons)

    @property
    def not_enough_history(self) -> bool:
        return self.evaluated < MIN_VALID_SEASONS

    @property
    def typical_warm_flowering_nights(self) -> float | None:
        """Median count of warm nights during flowering across the evaluated seasons."""
        counts = [
            s.warm_flowering_nights for s in self.seasons if s.warm_flowering_nights is not None
        ]
        return statistics.median(counts) if counts else None

    @property
    def typical_cycle_rain_mm(self) -> float | None:
        """Median rain over the cycle across the evaluated seasons (a typical year)."""
        totals = [s.cycle_rain_mm for s in self.seasons if s.cycle_rain_mm is not None]
        return statistics.median(totals) if totals else None

    @property
    def failed_years(self) -> int:
        return sum(s.outcome == "fail" for s in self.seasons)

    @property
    def failure_rate(self) -> float:
        """failed / evaluated, 0 when nothing was evaluated (not_enough_history says why)."""
        return self.failed_years / self.evaluated if self.evaluated else 0.0

    def cause_summaries(self) -> tuple[CauseSummary, ...]:
        """Causes seen at least once: causes that failed a year first, then by how often, then
        name. A rare fail matters more to the farmer than a frequent stress (agro-logic review)."""
        by_cause: dict[Cause, list[tuple[int, Finding]]] = {}
        for s in self.seasons:
            for f in s.findings:
                by_cause.setdefault(f.cause, []).append((s.year, f))
        summaries = []
        for cause, hits in by_cause.items():
            worst_year, worst = max(
                hits, key=lambda h: (_SEVERITY_RANK[h[1].severity], h[1].badness)
            )
            summaries.append(
                CauseSummary(
                    cause=cause,
                    severity=worst.severity,
                    years=tuple(y for y, _ in hits),
                    worst_year=worst_year,
                    worst=worst,
                )
            )
        return tuple(
            sorted(
                summaries,
                key=lambda c: (-_SEVERITY_RANK[c.severity], -len(c.years), c.cause),
            )
        )


def too_wet_for(plan: PlanRiskResult, crop: CropProfile) -> bool:
    """A typical season here gets more rain than the crop survives (EcoCrop rainfall abs_max).

    Not a yearly check (cycle_rain_high was dropped: it flagged crops grown here, like maize,
    against the optimum). This only catches crops whose absolute limit is far below the local
    rain, e.g. sorghum (700 mm) at Los Chiles (~1,300 mm over May–Sep): the yearly checks find no
    "failures" there, yet the crop doesn't belong (agro-logic review 2026-11-15)."""
    typical = plan.typical_cycle_rain_mm
    return typical is not None and typical > crop.rainfall_mm.abs_max


# ------------------------------------------------------------------ season mechanics


def sowing_date(year: int, month: int, day: int) -> date:
    """The sowing day in a given year. Feb 29 falls back to Feb 28 in non-leap years."""
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def harvest_date(sown: date, crop: CropProfile) -> date:
    return sown + timedelta(days=crop.cycle_days)


@dataclass(frozen=True)
class _Stages:
    """Index ranges into the season's days (start inclusive, end exclusive)."""

    establishment: range
    flowering: range
    harvest: range


def stages(crop: CropProfile) -> _Stages:
    cycle_days = crop.cycle_days
    if cycle_days < ESTABLISHMENT_DAYS + HARVEST_WINDOW_DAYS:
        raise DomainInvariantError(f"cycle_days {cycle_days} is too short for the stage windows")
    start, end = FLOWERING_FRACTIONS.get(crop.id, DEFAULT_FLOWERING_FRACTIONS)
    return _Stages(
        establishment=range(0, ESTABLISHMENT_DAYS),
        flowering=range(math.floor(cycle_days * start), math.ceil(cycle_days * end)),
        harvest=range(cycle_days - HARVEST_WINDOW_DAYS, cycle_days),
    )


def flowering_heat_limit_c(crop: CropProfile) -> float:
    return FLOWERING_HEAT_LIMIT_C.get(crop.id, crop.temperature_c.abs_max)


def _present(values: Sequence[float]) -> list[float]:
    return [v for v in values if not math.isnan(v)]


def _window_total(values: Sequence[float]) -> float | None:
    """Total over the window, rescaled from the days present (few gaps allowed). None if empty."""
    present = _present(values)
    return sum(present) * len(values) / len(present) if present else None


def _mean(values: Sequence[float]) -> float | None:
    present = _present(values)
    return sum(present) / len(present) if present else None


def _longest_dry_span(rain_mm: Sequence[float]) -> range:
    """Indices of the longest run of consecutive dry days (the first one on ties; empty if none).
    A missing day ends the run: we can't call it dry."""
    best = range(0)
    start = 0
    for i, v in enumerate(rain_mm):
        if math.isnan(v) or v >= DRY_DAY_MM:
            start = i + 1
        elif i + 1 - start > len(best):
            best = range(start, i + 1)
    return best


def _longest_dry_run(rain_mm: Sequence[float]) -> int:
    return len(_longest_dry_span(rain_mm))


# ------------------------------------------------------------------ checks (one per cause)


@dataclass(frozen=True)
class SeasonDays:
    """One season's daily values, day 0 = sowing day."""

    rain_mm: tuple[float, ...]
    tmax_c: tuple[float, ...]
    root_wetness: tuple[float, ...]
    tmin_c: tuple[float, ...] = ()  # empty = no night temperatures


def _slice(values: tuple[float, ...], r: range) -> tuple[float, ...]:
    return values[r.start : r.stop]


def check_late_dry_start(days: SeasonDays, st: _Stages) -> Finding | None:
    rain = _slice(days.rain_mm, st.establishment)
    total = _window_total(rain)
    dry_run = _longest_dry_run(rain)
    if total is None:
        return None
    low = total < ESTABLISHMENT_RAIN_STRESS_MM
    long_dry = dry_run >= ESTABLISHMENT_DRY_RUN_DAYS
    if not (low or long_dry):
        return None
    severity: Severity = "fail" if total < ESTABLISHMENT_RAIN_FAIL_MM else "stress"
    window = Text(
        f"in the first {ESTABLISHMENT_DAYS} days after sowing",
        f"en los primeros {ESTABLISHMENT_DAYS} días después de la siembra",
    )
    mm = num(total)
    rain_part = Text(f"only {mm.en} mm of rain", f"solo {mm.es} mm de lluvia")
    dry_part = Text(f"{dry_run} days in a row without rain", f"{dry_run} días seguidos sin lluvia")
    if low and long_dry:
        what = Text(f"{rain_part.en} and {dry_part.en}", f"{rain_part.es} y {dry_part.es}")
    else:
        what = rain_part if low else dry_part
    return Finding(
        cause="late_dry_start",
        severity=severity,
        badness=-total,  # less rain = worse
        evidence=Text(f"{what.en} {window.en}", f"{what.es} {window.es}"),
    )


def _dry_spell_severity(dry_run: int, driest: float | None) -> Severity | None:
    if dry_run < FLOWERING_DRY_STRESS_DAYS:
        return None
    if dry_run >= FLOWERING_DRY_ALWAYS_FAIL_DAYS:
        return "fail"
    if driest is None:  # no wetness data for the run: length alone decides
        return "fail" if dry_run >= FLOWERING_DRY_FAIL_DAYS else "stress"
    if dry_run >= FLOWERING_DRY_FAIL_DAYS and driest < FLOWERING_DRY_FAIL_WETNESS:
        return "fail"
    return "stress" if driest < FLOWERING_DRY_STRESS_WETNESS else None


def check_flowering_dry_spell(days: SeasonDays, st: _Stages) -> Finding | None:
    flowering_rain = _slice(days.rain_mm, st.flowering)
    span = _longest_dry_span(flowering_rain)
    dry_run = len(span)
    run_days = range(st.flowering.start + span.start, st.flowering.start + span.stop)
    wetness = _present(_slice(days.root_wetness, run_days))
    driest = min(wetness) if wetness else None
    severity = _dry_spell_severity(dry_run, driest)
    if severity is None:
        return None
    evidence = Text(
        f"{dry_run} days in a row without rain during flowering",
        f"{dry_run} días seguidos sin lluvia durante la floración",
    )
    if driest is not None and driest < FLOWERING_DRY_STRESS_WETNESS:
        evidence = Text(
            f"{evidence.en}, and the soil dried to {pct(driest).en} (100% = soaked; "
            "model estimate)",
            f"{evidence.es}, y el suelo se secó hasta {pct(driest).es} (100 % = empapado; "
            "estimación de modelo)",
        )
    return Finding(
        cause="flowering_dry_spell", severity=severity, badness=float(dry_run), evidence=evidence
    )


def check_cycle_rain_low(days: SeasonDays, crop: CropProfile) -> Finding | None:
    total = _window_total(days.rain_mm)
    minimum = crop.rainfall_mm.abs_min
    if total is None or total >= minimum:
        return None
    second_half = range(crop.cycle_days // 2, crop.cycle_days)
    wetness = _mean(_slice(days.root_wetness, second_half))
    drying = wetness is not None and wetness < CYCLE_LOW_SOIL_WETNESS
    mm, least = num(total), num(minimum)
    # EcoCrop's minimum is FAO's annual figure applied per cycle here (docs/sources/ecocrop.md):
    # "usually given for" + "(FAO)", not "needs at least" (farmer-language review 2026-11-15).
    head = Text(
        f"only {mm.en} mm of rain over the whole cycle, below the {least.en} mm usually given "
        f"for {crop.name.lower()} (FAO)",
        f"solo {mm.es} mm de lluvia en todo el ciclo, menos de los {least.es} mm que se suelen "
        f"indicar para {crop.the_es} (FAO)",
    )
    if drying and wetness is not None:
        tail = Text(
            f". The soil dried out ({pct(wetness).en}; 100% = soaked; model estimate)",
            f". El suelo se secó ({pct(wetness).es}; 100 % = empapado; estimación de modelo)",
        )
    else:
        tail = Text(
            ". The crop would have depended on moisture left in the soil",
            ". El cultivo habría dependido de la humedad que quedaba en el suelo",
        )
    return Finding(
        cause="cycle_rain_low",
        severity="fail" if drying else "stress",
        badness=minimum - total,
        evidence=Text(head.en + tail.en, head.es + tail.es),
    )


def check_harvest_wet(days: SeasonDays, st: _Stages, crop: CropProfile) -> Finding | None:
    total = _window_total(_slice(days.rain_mm, st.harvest))
    stress_mm, fail_mm = HARVEST_RAIN_MM.get(crop.id, DEFAULT_HARVEST_RAIN_MM)
    if total is None or total < stress_mm:
        return None
    severity: Severity = "fail" if fail_mm is not None and total >= fail_mm else "stress"
    wetness = _mean(_slice(days.root_wetness, st.harvest))
    soggy = crop.needs_good_drainage and wetness is not None and wetness >= HARVEST_SOIL_WETNESS
    mm = num(total)
    what = Text(f"{mm.en} mm of rain", f"{mm.es} mm de lluvia")
    if soggy and wetness is not None:
        w = pct(wetness)
        what = Text(
            f"{what.en} and the soil almost soaked ({w.en})",
            f"{what.es} y el suelo casi empapado ({w.es})",
        )
    return Finding(
        cause="harvest_wet",
        severity=severity,
        badness=total,
        evidence=Text(
            f"{what.en} in the last {HARVEST_WINDOW_DAYS} days before harvest",
            f"{what.es} en los últimos {HARVEST_WINDOW_DAYS} días antes de la cosecha",
        ),
    )


def check_flowering_heat(days: SeasonDays, st: _Stages, crop: CropProfile) -> Finding | None:
    limit = flowering_heat_limit_c(crop)
    hot = sum(1 for t in _slice(days.tmax_c, st.flowering) if not math.isnan(t) and t > limit)
    if hot < FLOWERING_HEAT_STRESS_DAYS:
        return None
    lim = num(limit)
    return Finding(
        cause="flowering_heat",
        severity="fail" if hot >= FLOWERING_HEAT_FAIL_DAYS else "stress",
        badness=float(hot),
        evidence=Text(
            f"{hot} days above {lim.en} °C during flowering",
            f"{hot} días con más de {lim.es} °C durante la floración",
        ),
    )


def warm_flowering_nights(days: SeasonDays, crop: CropProfile) -> int | None:
    """Nights above WARM_NIGHT_C during flowering, or None without night temperatures."""
    nights = _present(_slice(days.tmin_c, stages(crop).flowering))
    return sum(1 for t in nights if t > WARM_NIGHT_C) if nights else None


def warm_nights_are_typical(plan: PlanRiskResult, crop: CropProfile) -> bool:
    """Beans/cowpea where a typical season has WARM_NIGHT_NOTE_NIGHTS or more warm nights."""
    typical = plan.typical_warm_flowering_nights
    return crop.id in WARM_NIGHT_CROPS and typical is not None and typical >= WARM_NIGHT_NOTE_NIGHTS


def evaluate_season(days: SeasonDays, crop: CropProfile) -> tuple[Finding, ...]:
    """Every check for one season, in a fixed order (stage order through the cycle)."""
    st = stages(crop)
    found = (
        check_late_dry_start(days, st),
        check_flowering_dry_spell(days, st),
        check_flowering_heat(days, st, crop),
        check_cycle_rain_low(days, crop),
        check_harvest_wet(days, st, crop),
    )
    return tuple(f for f in found if f is not None)


# ------------------------------------------------------------------ the whole history


def season_days(history: DailyHistory, sown: date, cycle_days: int) -> SeasonDays | None:
    """The season's days, or None if not fully inside the history or too much rain is missing."""
    first = history.offset(sown)
    last = first + cycle_days  # exclusive
    if first < 0 or last > len(history.rain_mm):
        return None
    rain = history.rain_mm[first:last]
    missing = sum(1 for v in rain if math.isnan(v))
    if missing / cycle_days >= MAX_MISSING_RAIN_FRACTION:
        return None
    return SeasonDays(
        rain_mm=rain,
        tmax_c=history.tmax_c[first:last],
        root_wetness=history.root_wetness[first:last],
        tmin_c=history.tmin_c[first:last],
    )


def stress_test(
    *, history: DailyHistory, crop: CropProfile, sowing_month: int, sowing_day: int
) -> PlanRiskResult:
    """Replay 'sow `crop` every year on this date' over the history, one result per season."""
    if not 1 <= sowing_month <= 12 or not 1 <= sowing_day <= 31:
        raise DomainInvariantError(f"Invalid sowing date {sowing_month}-{sowing_day}")
    seasons: list[SeasonResult] = []
    skipped: list[int] = []
    for year in range(history.start.year, history.end.year + 1):
        sown = sowing_date(year, sowing_month, sowing_day)
        if sown < history.start:
            continue  # before the history starts: not a season we could have seen
        days = season_days(history, sown, crop.cycle_days)
        if days is None:
            if harvest_date(sown, crop) <= history.end + timedelta(days=1):
                skipped.append(year)  # in range but with gaps; the latest unfinished one is not
            continue
        seasons.append(
            SeasonResult(
                year=year,
                findings=evaluate_season(days, crop),
                cycle_rain_mm=_window_total(days.rain_mm),
                warm_flowering_nights=warm_flowering_nights(days, crop),
            )
        )
    return PlanRiskResult(
        crop_id=crop.id,
        sowing_month=sowing_month,
        sowing_day=sowing_day,
        seasons=tuple(seasons),
        skipped_years=tuple(skipped),
    )
