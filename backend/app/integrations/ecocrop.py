"""Crop tolerance ranges from local FAO EcoCrop subsets (annual and permanent crops).

The CSVs (data/ecocrop_subset.csv, data/perennial_crops.csv) are versioned so the app never needs
the network for crop data.
Rows with verified=false still have approximate values: check them against the EcoCrop
source and flip the flag (see docs/sources/ecocrop.md).
"""

from __future__ import annotations

import csv
from functools import cached_property
from pathlib import Path

from app.domain.models import CropProfile, PerennialCropProfile, Range
from app.errors import ConfigError, DomainInvariantError

SOURCE = "ecocrop_subset"


def _range(row: dict[str, str], prefix: str) -> Range:
    return Range(
        abs_min=float(row[f"{prefix}_abs_min"]),
        opt_min=float(row[f"{prefix}_opt_min"]),
        opt_max=float(row[f"{prefix}_opt_max"]),
        abs_max=float(row[f"{prefix}_abs_max"]),
    )


def _bool(v: str) -> bool:
    return v.strip().lower() in {"true", "1", "yes"}


def _sources(v: str) -> tuple[str, ...]:
    """'FAO EcoCrop; FAO-56 Table 22' → ('FAO EcoCrop', 'FAO-56 Table 22')."""
    return tuple(s.strip() for s in v.split(";") if s.strip())


class EcoCropCatalog:
    name = SOURCE

    def __init__(self, path: Path) -> None:
        self.path = path

    @cached_property
    def _crops(self) -> dict[str, CropProfile]:
        try:
            with self.path.open(encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
        except FileNotFoundError as e:
            raise ConfigError(
                f"Crop catalog not found: {self.path}",
                details={"source": SOURCE, "file": self.path.name},
            ) from e
        crops: dict[str, CropProfile] = {}
        for i, row in enumerate(rows, start=2):
            try:
                crop = CropProfile(
                    id=row["id"].strip(),
                    name=row["name"].strip(),
                    name_es=row["name_es"].strip() or None,
                    gender_es=row["gender_es"].strip(),
                    scientific_name=row["scientific_name"].strip(),
                    family=row["family"].strip(),
                    is_legume=_bool(row["is_legume"]),
                    cycle_days=int(row["cycle_days"]),
                    temperature_c=_range(row, "temp"),
                    rainfall_mm=_range(row, "rain"),
                    soil_ph=_range(row, "ph"),
                    root_depth_m=float(row["root_depth_m"]),
                    is_cover_crop=_bool(row["is_cover_crop"]),
                    needs_good_drainage=_bool(row["needs_good_drainage"]),
                    forage_value=float(row["forage_value"]),
                    nutrition_density=float(row["nutrition_density"]),
                    mycorrhizal_affinity=float(row["mycorrhizal_affinity"]),
                    nitrogen_demand=float(row["nitrogen_demand"]),
                    market_note=row["market_note"].strip(),
                    sources=_sources(row["sources"]),
                    verified=_bool(row.get("verified", "false")),
                )
            # Short rows give None values (AttributeError on .strip, TypeError on float).
            except (KeyError, ValueError, TypeError, AttributeError, DomainInvariantError) as e:
                raise ConfigError(
                    f"{self.path.name} line {i} is invalid: {e}",
                    details={"source": SOURCE, "file": self.path.name, "line": i},
                ) from e
            if crop.id in crops:
                raise ConfigError(
                    f"{self.path.name} line {i}: duplicate crop id '{crop.id}'",
                    details={"source": SOURCE, "file": self.path.name, "line": i},
                )
            crops[crop.id] = crop
        return crops

    def all(self) -> dict[str, CropProfile]:
        return self._crops


PERENNIAL_SOURCE = "ecocrop_perennials"


class PerennialCropCatalog:
    """Permanent crops (cacao, coffee…) from data/perennial_crops.csv, same EcoCrop import."""

    name = PERENNIAL_SOURCE

    def __init__(self, path: Path) -> None:
        self.path = path

    @cached_property
    def _crops(self) -> dict[str, PerennialCropProfile]:
        try:
            with self.path.open(encoding="utf-8", newline="") as f:
                rows = list(csv.DictReader(f))
        except FileNotFoundError as e:
            raise ConfigError(
                f"Permanent crop catalog not found: {self.path}",
                details={"source": PERENNIAL_SOURCE, "file": self.path.name},
            ) from e
        crops: dict[str, PerennialCropProfile] = {}
        for i, row in enumerate(rows, start=2):
            try:
                altitude = row["max_altitude_m"].strip()
                crop = PerennialCropProfile(
                    id=row["id"].strip(),
                    name=row["name"].strip(),
                    name_es=row["name_es"].strip() or None,
                    gender_es=row["gender_es"].strip(),
                    scientific_name=row["scientific_name"].strip(),
                    family=row["family"].strip(),
                    temperature_c=_range(row, "temp"),
                    rainfall_mm=_range(row, "rain"),
                    soil_ph=_range(row, "ph"),
                    max_altitude_m=float(altitude) if altitude else None,
                    sources=_sources(row["sources"]),
                    verified=_bool(row.get("verified", "false")),
                )
            # Short rows give None values (AttributeError on .strip, TypeError on float).
            except (KeyError, ValueError, TypeError, AttributeError, DomainInvariantError) as e:
                raise ConfigError(
                    f"{self.path.name} line {i} is invalid: {e}",
                    details={"source": PERENNIAL_SOURCE, "file": self.path.name, "line": i},
                ) from e
            if crop.id in crops:
                raise ConfigError(
                    f"{self.path.name} line {i}: duplicate crop id '{crop.id}'",
                    details={"source": PERENNIAL_SOURCE, "file": self.path.name, "line": i},
                )
            crops[crop.id] = crop
        return crops

    def all(self) -> dict[str, PerennialCropProfile]:
        return self._crops
