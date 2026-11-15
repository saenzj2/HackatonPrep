"""Refresh the crop tolerance ranges in data/ecocrop_subset.csv from FAO EcoCrop.

Source: the EcoCrop table published by the Adaptation Atlas (CGIAR) as Parquet. Only the
temperature, rainfall and pH ranges and `needs_good_drainage` (from the drainage classes the crop
tolerates) come from EcoCrop; every other column is kept as it is.
Rows are matched by EcoCrop `ecoportcode` (ECOPORT_CODES), never by name: EcoCrop has several
entries per species (subspecies, varieties).

Run it by hand when the source or the crop list changes (needs: pip install -e ".[data]"):
    cd backend && .venv/bin/python -m scripts.import_ecocrop --download
    cd backend && .venv/bin/python -m scripts.import_ecocrop --parquet path/to/ecocrop.parquet
Add --write-fixture to refresh tests/fixtures/ecocrop/ after checking the diff.
The app never calls this: it reads the CSV, so the demo works offline.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import tempfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.settings import BACKEND_DIR

log = logging.getLogger(__name__)

ECOCROP_URL = "https://digital-atlas.s3.amazonaws.com/cdh/data/ecocrop/ecocrop.parquet"
CSV_PATH = BACKEND_DIR / "data" / "ecocrop_subset.csv"
FIXTURE_PATH = BACKEND_DIR / "tests" / "fixtures" / "ecocrop" / "ecocrop_records.json"

# Our crop id → EcoCrop ecoportcode (the main entry for the species, checked by hand).
ECOPORT_CODES = {
    "rice": 1574,  # Oryza sativa
    "beans": 1668,  # Phaseolus vulgaris
    "maize": 238663,  # Zea mays ssp. mays (entry 2175 "Zea mays" has empty fields)
    "sorghum": 48747,  # Sorghum bicolor
    "cowpea": 2153,  # Vigna unguiculata
}

# Our CSV column → EcoCrop column. Units: °C, mm (EcoCrop: annual rainfall, see
# docs/sources/ecocrop.md for how the app uses it), pH.
RANGE_COLUMNS = {
    "temp_abs_min": "tmin",
    "temp_opt_min": "topmn",
    "temp_opt_max": "topmx",
    "temp_abs_max": "tmax",
    "rain_abs_min": "rmin",
    "rain_opt_min": "ropmn",
    "rain_opt_max": "ropmx",
    "rain_abs_max": "rmax",
    "ph_abs_min": "phmin",
    "ph_opt_min": "phopmn",
    "ph_opt_max": "phopmx",
    "ph_abs_max": "phmax",
}
# `drar`: soil drainage classes the crop tolerates (a list),
# e.g. ["poorly (saturated >50% of year)"] for rice.
LIST_COLUMNS = ["drar"]
FIXTURE_COLUMNS = [
    "ecoportcode",
    "scientificname",
    *RANGE_COLUMNS.values(),
    "gmin",
    "gmax",
    *LIST_COLUMNS,
]
DRAINAGE_COLUMN = "needs_good_drainage"  # our CSV column, after is_cover_crop
SOURCE_PREFIX = "FAO EcoCrop"  # any old EcoCrop citation in `sources` is replaced


def load_records(parquet: Path) -> dict[int, dict[str, Any]]:
    """EcoCrop rows for ECOPORT_CODES, keyed by ecoportcode, as plain JSON-able values."""
    import pandas as pd  # noqa: PLC0415  (only this script needs pandas + pyarrow)

    df = pd.read_parquet(parquet)
    rows = df[df["ecoportcode"].isin(ECOPORT_CODES.values())]
    records: dict[int, dict[str, Any]] = {}
    for _, row in rows.iterrows():
        record: dict[str, Any] = {}
        for column in FIXTURE_COLUMNS:
            value = row[column]
            # numpy/pandas scalars → plain Python, missing → None (the fixture is JSON)
            if column in LIST_COLUMNS:
                record[column] = None if value is None else [str(v) for v in value]
                continue
            record[column] = None if pd.isna(value) else getattr(value, "item", lambda v=value: v)()
        records[int(row["ecoportcode"])] = record
    missing = set(ECOPORT_CODES.values()) - set(records)
    if missing:
        raise SystemExit(f"EcoCrop file has no rows for ecoportcode {sorted(missing)}")
    return records


def _number(value: Any) -> str:
    """12 → '12', 5.5 → '5.5', 8.0 → '8.0' (CSV text, same style as the file)."""
    return str(value)


def _sources(old: str, code: int, fetched: str) -> str:
    kept = [
        s.strip() for s in old.split(";") if s.strip() and not s.strip().startswith(SOURCE_PREFIX)
    ]
    ecocrop = (
        f"{SOURCE_PREFIX} ecoportcode {code} via Adaptation Atlas parquet "
        f"(tolerance ranges, {fetched})"
    )
    return "; ".join([ecocrop, *kept])


def needs_good_drainage(record: dict[str, Any]) -> bool:
    """True unless EcoCrop says the crop tolerates poorly drained soil (e.g. rice)."""
    tolerated = record.get("drar")
    if not tolerated:
        raise SystemExit(f"EcoCrop {record['ecoportcode']} has no drainage classes (drar)")
    return not any(v.startswith("poorly") for v in tolerated)


def apply_ranges(
    rows: list[dict[str, str]], records: dict[int, dict[str, Any]], fetched: str
) -> list[dict[str, str]]:
    """New CSV rows: EcoCrop ranges, EcoCrop cited first in `sources`, verified=true.

    Only crops in ECOPORT_CODES change; every other column and row is kept as it is.
    """
    out = []
    for row in rows:
        code = ECOPORT_CODES.get(row["id"])
        if code is None:
            out.append(dict(row))
            continue
        record = records[code]
        empty = [c for c in RANGE_COLUMNS.values() if record[c] is None]
        if empty:
            raise SystemExit(f"{row['id']}: EcoCrop {code} has empty {empty}")
        new = dict(row)
        for ours, theirs in RANGE_COLUMNS.items():
            new[ours] = _number(record[theirs])
        new["sources"] = _sources(row["sources"], code, fetched)
        new[DRAINAGE_COLUMN] = "true" if needs_good_drainage(record) else "false"
        new["verified"] = "true"
        out.append(new)
    return out


def _download(dest_dir: Path) -> Path:
    dest = dest_dir / "ecocrop.parquet"
    log.info("downloading %s", ECOCROP_URL)
    urllib.request.urlretrieve(ECOCROP_URL, dest)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--parquet", type=Path, help="a local copy of ecocrop.parquet")
    source.add_argument("--download", action="store_true", help=f"download {ECOCROP_URL}")
    parser.add_argument("--fetched", help="date the file was downloaded (default: today, UTC)")
    parser.add_argument("--write-fixture", action="store_true", help="also refresh the fixture")
    args = parser.parse_args()
    fetched = args.fetched or datetime.now(UTC).date().isoformat()

    with tempfile.TemporaryDirectory() as tmp:
        parquet = _download(Path(tmp)) if args.download else args.parquet
        records = load_records(parquet)

    with CSV_PATH.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        if DRAINAGE_COLUMN not in header:
            header.insert(header.index("is_cover_crop") + 1, DRAINAGE_COLUMN)
        rows = list(reader)
    new_rows = apply_ranges(rows, records, fetched)
    with CSV_PATH.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(new_rows)
    log.info(
        "wrote %s (%d crops from EcoCrop)", CSV_PATH.relative_to(BACKEND_DIR), len(ECOPORT_CODES)
    )

    if args.write_fixture:
        FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
        payload = {"source": ECOCROP_URL, "fetched": fetched, "records": list(records.values())}
        FIXTURE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        log.info("wrote %s", FIXTURE_PATH.relative_to(BACKEND_DIR))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
