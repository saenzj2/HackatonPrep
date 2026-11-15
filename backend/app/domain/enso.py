"""El Niño / La Niña context for plan-risk: label each sowing year and split failures by phase.

The index is NOAA CPC's Relative Oceanic Niño Index (RONI), official since 2026-02-01; the legacy
ONI is only used to count years it would label differently (docs/sources/noaa_enso.md).
Pure: the adapter parses the text file into an `EnsoIndex`.

Never a forecast and never "El Niño = drought": the split reports what this point's own history
shows, and says when there are too few years to compare.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal

from app.domain.plan_risk import PlanRiskResult
from app.domain.text import Text, month, month_span
from app.errors import DomainInvariantError

EnsoPhase = Literal["el_nino", "la_nina", "neutral"]
PHASES: tuple[EnsoPhase, ...] = ("el_nino", "la_nina", "neutral")

# 3-month seasons in file order; the m-th is centred on month m (DJF → January).
SEASONS = ("DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ")

# NOAA's El Niño / La Niña threshold on the 3-month index (°C). NOAA's *episode* definition also
# needs 5 consecutive overlapping seasons; plan-risk labels a sowing year by the single season
# centred on the sowing month. Placeholder rule (plan-risk.md, phase 6; decisions.md).
ENSO_THRESHOLD_C = 0.5
# Below this many evaluated years in a phase, the note says there is too little data to compare.
# Placeholder (plan-risk.md, phase 6).
MIN_YEARS_TO_COMPARE = 4


@dataclass(frozen=True)
class EnsoSeason:
    season: str  # "ASO"
    year: int  # year of the season's middle month (NOAA's YR column)
    anomaly_c: float


@dataclass(frozen=True)
class EnsoIndex:
    name: str  # "RONI" or "ONI"
    seasons: tuple[EnsoSeason, ...]  # file order, oldest first

    def __post_init__(self) -> None:
        if not self.seasons:
            raise DomainInvariantError(f"{self.name} index has no seasons")

    @property
    def latest(self) -> EnsoSeason:
        return self.seasons[-1]

    def anomaly(self, year: int, month: int) -> float | None:
        """The index for the 3-month season centred on `month` of `year`, or None if absent."""
        season = SEASONS[month - 1]
        return next(
            (s.anomaly_c for s in self.seasons if s.year == year and s.season == season), None
        )


def phase_of(anomaly_c: float) -> EnsoPhase:
    if anomaly_c >= ENSO_THRESHOLD_C:
        return "el_nino"
    if anomaly_c <= -ENSO_THRESHOLD_C:
        return "la_nina"
    return "neutral"


def year_phase(index: EnsoIndex, year: int, month: int) -> EnsoPhase | None:
    """Phase of a sowing year: the season centred on the sowing month. None if not in the index."""
    anomaly = index.anomaly(year, month)
    return None if anomaly is None else phase_of(anomaly)


def label_disagreements(
    official: EnsoIndex, legacy: EnsoIndex, *, years: Iterable[int], month: int
) -> int:
    """How many of these sowing years the legacy index labels differently."""
    return sum(
        1
        for y in years
        if (a := year_phase(official, y, month)) is not None
        and (b := year_phase(legacy, y, month)) is not None
        and a != b
    )


@dataclass(frozen=True)
class PhaseCount:
    years: int  # evaluated sowing years in this phase
    failed: int


@dataclass(frozen=True)
class EnsoSplit:
    counts: dict[EnsoPhase, PhaseCount]
    note: Text


PHASE_NAMES: dict[EnsoPhase, Text] = {
    "el_nino": Text("El Niño", "El Niño"),
    "la_nina": Text("La Niña", "La Niña"),
    "neutral": Text("normal", "normales"),  # "neutral" is jargon for farmers (IMN says it too)
}


def enso_split(plan: PlanRiskResult, index: EnsoIndex) -> EnsoSplit:
    """Failed years per ENSO phase of the sowing season, with a note that never claims
    significance and says when a phase has too few years to compare."""
    counts: dict[EnsoPhase, PhaseCount] = {}
    for phase in PHASES:
        seasons = [s for s in plan.seasons if year_phase(index, s.year, plan.sowing_month) == phase]
        counts[phase] = PhaseCount(
            years=len(seasons), failed=sum(s.outcome == "fail" for s in seasons)
        )
    return EnsoSplit(counts=counts, note=_split_note(counts))


def _years(n: int, phase: Text) -> Text:
    """'1 El Niño year' / '1 año de El Niño', plural otherwise."""
    if n == 1:
        return Text(f"1 {phase.en} year", f"1 año de {phase.es}")
    return Text(f"{n} {phase.en} years", f"{n} años de {phase.es}")


def _split_note(counts: dict[EnsoPhase, PhaseCount]) -> Text:
    few: list[EnsoPhase] = [p for p in PHASES[:2] if counts[p].years < MIN_YEARS_TO_COMPARE]
    if few:
        en = " and ".join(_years(counts[p].years, PHASE_NAMES[p]).en for p in few)
        es = " y ".join(_years(counts[p].years, PHASE_NAMES[p]).es for p in few)
        return Text(
            f"Only {en} with this sowing date, not enough to compare",
            f"Solo hubo {es} con esta fecha de siembra: no alcanza para comparar",
        )
    parts_en, parts_es = [], []
    for phase in PHASES:
        c, name = counts[phase], PHASE_NAMES[phase]
        parts_en.append(f"{c.failed} of {c.years} {name.en} years")
        if phase == "neutral":
            parts_es.append(f"{c.failed} de {c.years} años {name.es}")
        else:
            parts_es.append(f"{c.failed} de {c.years} años de {name.es}")
    # Conditional ("would have failed"), the subject said, "and" before the last item, and a
    # small-sample warning: 26 years split three ways is always few (farmer-language review).
    return Text(
        f"This planting would have failed in {', '.join(parts_en[:-1])} and {parts_en[-1]}. "
        "Few years, so this may be chance: a pattern in past years, not a forecast",
        f"Esta siembra habría fallado en {', '.join(parts_es[:-1])} y {parts_es[-1]}. "
        "Son pocos años y puede ser casualidad: es un patrón de años pasados, no un pronóstico",
    )


# --- Data-gap notes ----------------------------------------------------------------------------
ENSO_UNAVAILABLE = Text(
    "El Niño data (NOAA) is not available right now, so years are not labelled by El Niño phase",
    "Los datos de El Niño (NOAA) no están disponibles en este momento, así que los años no se "
    "marcan por fase de El Niño",
)


def latest_estimate_note(index: EnsoIndex) -> Text:
    """NOAA revises the last ~2 values for up to two months (docs/sources/noaa_enso.md)."""
    s = index.latest
    span = season_span(s.season)
    return Text(
        "El Niño and La Niña years are labelled with NOAA's official ocean index (RONI). The "
        f"latest reading ({span.en} {s.year}) is preliminary and NOAA may adjust it for about "
        "two months. It describes now, not the coming season",
        "Los años de El Niño y La Niña se marcan con el índice oficial de NOAA sobre el océano "
        f"Pacífico (RONI). El último dato ({span.es} {s.year}) es preliminar y NOAA puede "
        "ajustarlo durante unos dos meses. Describe la situación actual, no es un pronóstico para "
        "la próxima temporada",
    )


def season_span(season: str) -> Text:
    """'ASO' → 'Aug–Oct' / 'ago–oct' (the 3-month season centred on its middle month)."""
    centre = SEASONS.index(season) + 1
    return month_span(((centre - 2) % 12 + 1, centre, centre % 12 + 1))


def disagreement_note(items: Sequence[tuple[int, int, int]]) -> Text:
    """One line for every sowing month: how many sowing years the legacy ONI would label
    differently (decisions.md 2026-11-15). `items` = (differing, total, sowing_month), in order."""
    parts_en = [f"{d} of {t} for {month(m).en}" for d, t, m in items]
    parts_es = [f"{d} de {t} en {month(m).es}" for d, t, m in items]
    some = any(d for d, _, _ in items)
    # "some", never "a few": 14 of 26 is not a few. The counts after the colon say how many.
    return Text(
        f"With NOAA's older index (ONI), {'some' if some else 'no'} years would change group "
        f"(El Niño, La Niña or normal): {', '.join(parts_en)}",
        f"Con el índice anterior de NOAA (ONI), {'algunos' if some else 'ningún'} "
        f"{'años cambiarían' if some else 'año cambiaría'} de grupo (El Niño, La Niña o normal): "
        f"{', '.join(parts_es)}",
    )
