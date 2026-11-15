"""Bilingual farmer-facing text (English + Costa Rican Spanish).

Every sentence a farmer or judge reads is built here or next to its rule as a `Text`, with both
languages side by side, so they never drift apart. The API sends it as {"en": ..., "es": ...}.
Helpers give month names, crop-family names and numbers in each language (Spanish uses a decimal
comma). Error messages are not farmer text: they stay English (docs/errors.md).

Spanish articles come from the crop's `gender_es` column ("el maíz", "la yuca"): use
`CropProfile.the_es` / `of_the_es`, never a hardcoded "el"/"del".
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Text:
    en: str
    es: str

    def lower(self) -> Text:
        """For a crop name in the middle of a sentence: 'Maize' → 'maize', 'Maíz' → 'maíz'."""
        return Text(self.en.lower(), self.es.lower())


MONTHS_EN = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip
MONTHS_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "setiembre",
    "octubre",
    "noviembre",
    "diciembre",
)  # fmt: skip  (Costa Rica writes "setiembre")
MONTHS_ABBR_EN = tuple(m[:3] for m in MONTHS_EN)
MONTHS_ABBR_ES = (
    "ene",
    "feb",
    "mar",
    "abr",
    "may",
    "jun",
    "jul",
    "ago",
    "set",
    "oct",
    "nov",
    "dic",
)

# Botanical family → plain name. Latin names mean nothing to most farmers.
FAMILIES = {
    "Poaceae": Text("grass family", "familia de las gramíneas"),
    "Fabaceae": Text("bean family", "familia de las leguminosas"),
    "Cucurbitaceae": Text("squash family", "familia de las cucurbitáceas"),
    "Solanaceae": Text("tomato family", "familia de las solanáceas"),
    "Brassicaceae": Text("cabbage family", "familia de las crucíferas"),
    "Amaranthaceae": Text("amaranth family", "familia de las amarantáceas"),
}


def month(m: int) -> Text:
    """Full month name, 1..12."""
    return Text(MONTHS_EN[m - 1], MONTHS_ES[m - 1])


def month_span(months: tuple[int, ...]) -> Text:
    """'Sep–Nov' / 'set–nov'."""
    first, last = months[0] - 1, months[-1] - 1
    return Text(
        f"{MONTHS_ABBR_EN[first]}–{MONTHS_ABBR_EN[last]}",
        f"{MONTHS_ABBR_ES[first]}–{MONTHS_ABBR_ES[last]}",
    )


def family(name: str) -> Text:
    """Plain family name; unknown families keep their botanical name."""
    return FAMILIES.get(name, Text(name, name))


def num(value: float, decimals: int = 0) -> Text:
    """1234.5 → '1234.5' / '1234,5' (Spanish decimal comma)."""
    s = f"{value:.{decimals}f}"
    return Text(s, s.replace(".", ","))


def pct(fraction: float) -> Text:
    """0.94 → '94%' / '94 %'."""
    n = round(fraction * 100)
    return Text(f"{n}%", f"{n} %")
