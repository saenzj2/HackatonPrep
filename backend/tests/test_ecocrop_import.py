"""EcoCrop import (scripts/import_ecocrop.py) and the committed crop CSV stay in sync.

Uses the saved EcoCrop records in tests/fixtures/ecocrop/ (real values, never hand-edited).
No network and no pyarrow: only the pure part of the script is tested.
"""

import csv

import pytest

from app.settings import BACKEND_DIR
from scripts.import_ecocrop import ECOPORT_CODES, RANGE_COLUMNS, apply_ranges
from tests.conftest import load_fixture

FIXTURE = load_fixture("ecocrop/ecocrop_records.json")
RECORDS = {r["ecoportcode"]: r for r in FIXTURE["records"]}


def _csv_rows() -> list[dict[str, str]]:
    with (BACKEND_DIR / "data" / "ecocrop_subset.csv").open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_committed_csv_has_the_ecocrop_ranges():
    """Fails if someone edits a range by hand: rerun the import instead."""
    rows = {r["id"]: r for r in _csv_rows()}
    for crop_id, code in ECOPORT_CODES.items():
        for ours, theirs in RANGE_COLUMNS.items():
            assert float(rows[crop_id][ours]) == pytest.approx(RECORDS[code][theirs]), (
                crop_id,
                ours,
            )
        assert rows[crop_id]["verified"] == "true"
        assert rows[crop_id]["sources"].startswith(f"FAO EcoCrop ecoportcode {code} ")


def test_import_replaces_ranges_and_old_citation_only():
    old = {
        "id": "sorghum",
        "rain_abs_max": "3000",
        "root_depth_m": "2.0",
        "sources": "FAO EcoCrop (tolerance ranges, approximate); FAO-56 Table 22 (root depth)",
        "verified": "false",
        **{k: "1" for k in RANGE_COLUMNS if k != "rain_abs_max"},
    }
    other_crop = {"id": "amaranth", "sources": "someone else", "verified": "false"}
    new, untouched = apply_ranges([old, other_crop], RECORDS, fetched="2026-11-14")
    assert new["rain_abs_max"] == "700"  # EcoCrop sorghum, ecoportcode 48747
    assert new["root_depth_m"] == "2.0"
    assert new["sources"] == (
        "FAO EcoCrop ecoportcode 48747 via Adaptation Atlas parquet "
        "(tolerance ranges, 2026-11-14); "
        "FAO-56 Table 22 (root depth)"
    )
    assert new["verified"] == "true"
    assert untouched == other_crop


def test_import_refuses_an_ecocrop_record_with_empty_ranges():
    records = {**RECORDS, 48747: {**RECORDS[48747], "rmax": None}}
    with pytest.raises(SystemExit, match="sorghum: EcoCrop 48747 has empty"):
        apply_ranges([{"id": "sorghum", "sources": "", "verified": "false"}], records, "x")
