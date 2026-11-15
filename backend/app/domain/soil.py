"""Derived soil properties: values computed from measured ones, never invented."""

from __future__ import annotations

# Clay, sand and silt are the three fine-earth fractions and add up to 100 % by definition.
FINE_EARTH_TOTAL_PCT = 100.0


def silt_pct(clay_pct: float | None, sand_pct: float | None) -> float | None:
    """Silt % = 100 - clay - sand, or None when that would not be a real measurement.

    None when either input is missing, outside 0..100, or when clay + sand exceeds 100 %. That
    last case happens because sources like OpenLandMap predict each fraction with its own model,
    so the two don't always add up. A negative silt would be an artifact, not a value.
    """
    if clay_pct is None or sand_pct is None:
        return None
    if not (0 <= clay_pct <= FINE_EARTH_TOTAL_PCT and 0 <= sand_pct <= FINE_EARTH_TOTAL_PCT):
        return None
    if clay_pct + sand_pct > FINE_EARTH_TOTAL_PCT:
        return None
    return FINE_EARTH_TOTAL_PCT - clay_pct - sand_pct
