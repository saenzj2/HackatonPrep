# FAO EcoCrop: crop tolerance ranges

| Field | Value |
|---|---|
| **Used for** | Crop temperature, rainfall and pH ranges (`CropSource`) |
| **Adapter** | `app/integrations/ecocrop.py` (reads the CSV; no network) |
| **Data** | `data/ecocrop_subset.csv` (versioned) |
| **Import** | `scripts/import_ecocrop.py` (run by hand; needs `pip install -e ".[data]"` for pyarrow) |
| **Source file** | `https://digital-atlas.s3.amazonaws.com/cdh/data/ecocrop/ecocrop.parquet`, fetched 2026-11-14 (2568 crops, 55 columns) |
| **Fixture** | `tests/fixtures/ecocrop/ecocrop_records.json` (the 5 rows we use, real values) |
| **Status** | ✅ Ranges from source for all 5 crops (`verified=true`) |

## Where the data comes from
FAO developed the ECOCROP database in 1999 and discontinued it around 2015; FAO now points to the
GAEZ platform ([FAO page](https://www.fao.org/geospatial/data-and-tools/data-portals/ecocrop/)).
We read the copy the **Adaptation Atlas** (CGIAR, led by the Alliance of Bioversity International
and CIAT) publishes as Parquet.

**License:** the Adaptation Atlas STAC catalog record lists **CC-BY-SA-4.0**, open access
([CGSpace record](https://cgspace.cgiar.org/items/df16ec75-be74-4a57-aeec-6534a5893779)). That record
doesn't name this file, so the license of `ecocrop.parquet` itself is **not confirmed**. Until it is:
credit "FAO ECOCROP via the Adaptation Atlas (CGIAR)" wherever the ranges are shown, and treat
`data/ecocrop_subset.csv` as a derivative under the same terms (attribution + share-alike).

## Rows used (one EcoCrop entry per crop, chosen by `ecoportcode`)
EcoCrop has several entries per species (subspecies, varieties), so rows are picked by code, never
by name. Mapping in `ECOPORT_CODES` (`scripts/import_ecocrop.py`).

| Our id | ecoportcode | EcoCrop name | Note |
|---|---|---|---|
| rice | 1574 | Oryza sativa | 2 more: ssp. indica (8143), ssp. javanica (8144) |
| beans | 1668 | Phaseolus vulgaris | |
| maize | 238663 | Zea mays ssp. mays | 2175 "Zea mays" has the same ranges but empty descriptive fields |
| sorghum | 48747 | Sorghum bicolor | 1982 is var. sweet |
| cowpea | 2153 | Vigna unguiculata | 6 subspecies entries |

## Columns
| Our CSV | EcoCrop | Unit |
|---|---|---|
| `temp_abs_min`, `temp_opt_min`, `temp_opt_max`, `temp_abs_max` | `tmin`, `topmn`, `topmx`, `tmax` | °C |
| `rain_abs_min`, `rain_opt_min`, `rain_opt_max`, `rain_abs_max` | `rmin`, `ropmn`, `ropmx`, `rmax` | mm, **annual** in FAO's definition (see below) |
| `ph_abs_min`, `ph_opt_min`, `ph_opt_max`, `ph_abs_max` | `phmin`, `phopmn`, `phopmx`, `phmax` | pH |

Not imported:
- `gmin`/`gmax` (cycle days): too wide to replace our single `cycle_days` (maize 65–365 days).
- `ktmp` (killing temperature): empty for almost every crop.
- The other columns (drainage, soil depth, texture, fertility, salinity, altitude, uses, …): left in
  the source file for later. Most promising:
  - **Soil needs per crop** (`text`, `dra`, `dep`): they pair with the real soil profile from
    OpenLandMap (`soil_profile`: texture class, clay, sand, field capacity; see decisions.md
    2026-11-14 "Soil profile from OpenLandMap") for a soil-suitability check.
  - **Use categories** (`cat`: "cover crop", "forage/pasture") to source `is_cover_crop` and `forage_value`.

**Soil pH:** scoring still uses the mock soil (`Sources.soil`). When the team switches it to
OpenLandMap pH, these EcoCrop pH ranges are what judge it, so pH results will move.

Every other CSV column (family, legume, cycle, root depth, traits, market note) is ours, not EcoCrop's;
see [`../crop-schema.md`](../crop-schema.md).

## Rainfall: annual in EcoCrop, compared per crop cycle in the app
FAO lists the rainfall ranges as **annual precipitation**. The app compares them with the rainfall
**over the crop cycle** (`cycle_rainfall_mm` in `suitability.py`). This was the method decided on
2026-11-06 and checked in the planting-windows review: read as annual, maize would score 0.22 in
San Carlos, which isn't credible. The EcoCrop R implementation (Recocrop) also turns the annual
values into per-month limits over the cycle. A per-month (driest-month) check is a possible
improvement; it changes results, so it needs its own `decisions.md` entry.

Known effect: every EcoCrop rice entry asks for 1500–2000 mm (flooded or irrigated rice), so rainfed
rice never fits by rainfall alone. Upland-rice values would need another source.

## Refresh
```bash
cd backend && .venv/bin/pip install -e ".[data]"
.venv/bin/python -m scripts.import_ecocrop --download --write-fixture   # or --parquet <file>
.venv/bin/python -m scripts.make_examples                               # example responses
make check
```
`tests/test_ecocrop_import.py` fails if a range in the CSV is edited by hand (it must match the
fixture). To add a crop: add its row to the CSV with our own columns, add its `ecoportcode` to
`ECOPORT_CODES`, then rerun the import with `--write-fixture`.

Rule: `abs_min ≤ opt_min ≤ opt_max ≤ abs_max`. The loader rejects rows that break it.

## To do
1. Add the crops the team picks for the pilot region. Crops with a cycle much longer than one
   season need a different rotation model (see decisions.md).
2. Optional: per-crop soil moisture and texture preferences (EcoCrop drainage, texture, depth).
3. **#24: add at least one mycorrhizal non-host** (`mycorrhizal_affinity` 0, e.g. amaranth or a
   Brassicaceae crop). Until then the `fungi_break` rotation rule (#25) can't fire with real data and
   is only covered by toy crops. `test_fungi_break_fires_with_real_crops` in `tests/test_integrations.py`
   is skipped until such a crop exists, then it runs by itself: check it passes.
4. Confirm the license of `ecocrop.parquet` with the Adaptation Atlas team.
