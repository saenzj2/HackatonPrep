# Crop schema (T3.1, #23)

> **Status: IMPLEMENTED for the 5 current crops, tolerance ranges from FAO EcoCrop.** The CSV, loader,
> `CropProfile`, `/crops` and the `Crop` schema in `api-contract.yaml` carry every field below.
> Design questions: answered (see the end). Trait values: team estimates until #24 cites them.

One row per crop in `data/ecocrop_subset.csv`. Every attribute the engine, the badges and the
explanations need lives here, so nothing about a crop is hardcoded in Python.

## Fields

**Existing columns (no change).** The loader already reads and validates them.

| Issue attribute | Column(s) | Type / unit | Used by |
|---|---|---|---|
| — | `id`, `name`, `scientific_name` | string; `id` is lowercase snake_case, unique | everything |
| Plant family | `family` | botanical family, Latin (`Fabaceae`) | rotation rules #25 (family succession, pest breaks) |
| Nitrogen fixing | `is_legume` | bool | rotation rules #25, legume bonus |
| Season length | `cycle_days` | int, days sowing → harvest | season fit (cycle longer than season = risk) |
| Temperature range | `temp_{abs_min,opt_min,opt_max,abs_max}` | °C | suitability scoring |
| Water need | `rain_{abs_min,opt_min,opt_max,abs_max}` | mm **over the crop cycle** | suitability scoring; `water_need` badge derived from `rain_opt_min` (no extra column) |
| — | `ph_{abs_min,opt_min,opt_max,abs_max}` | pH | suitability scoring, soil-test adjustment #32 |
| — | `verified` | bool; `true` once the tolerance ranges come from a cited source (EcoCrop import). Traits are labelled separately in `sources` | `data_gaps` in responses |

**New columns.**

| Issue attribute | Column | Type / allowed values | Meaning | Used by |
|---|---|---|---|---|
| Root depth | `root_depth_m` | float, metres | Typical maximum effective rooting depth (FAO-56 Table 22, upper value) | soil-health benefit ("deep roots open the subsoil"), rotation rules |
| *(EcoCrop)* Drainage | `needs_good_drainage` | bool | The crop doesn't tolerate poorly drained soil (EcoCrop `drar`); rice `false`, the rest `true` | waterlogging check in scoring |
| Cover-crop use | `is_cover_crop` | bool | Commonly grown to cover and protect the soil between cash crops | soil-health score, badges #38 |
| Forage value | `forage_value` | score 0..1 → API `{level, score}` | Value of the crop or its residue as animal feed | income/benefit text #29 |
| Nutrition density | `nutrition_density` | score 0..1 → API `{level, score}` | Nutrient density of the edible part (protein, micronutrients). 0 for non-food cover crops | nutrition badge #38 |
| Mycorrhizal affinity | `mycorrhizal_affinity` | score 0..1 → API `{level, score}` | How much the crop hosts and benefits from mycorrhizal fungi. 0 for non-hosts (Brassicaceae, Amaranthaceae) | fungi badge #38, practice cards #37, rule: non-host before a dependent crop |
| Market note | `market_note` | short text (≤ 120 chars), may be empty | One line of local market context, shown as-is | explanation #29 |
| *(not in issue)* Nutrient demand | `nitrogen_demand` | score 0..1 → API `{level, score}` | "Heavy feeder" = 1 | rule #25 "legumes after heavy feeders" needs it |
| *(not in issue)* Sources | `sources` | text: short citations separated by `;` | Where the row's values come from | #24 "every crop has a source", `evidence` |

### Trait scores: numbers inside, word + number in the API
The four trait columns are **0..1 scores** (1 = most) in the CSV and in `CropProfile`, so scoring can
use them directly. The API sends both, so the frontend can show the word and the number on hover:

```json
"forage_value": {"level": "medium", "score": 0.67}
```

The `Trait` type in `app/api/schemas.py` builds this from the score alone, using `level_for()`
(`app/domain/models.py`), so the word always matches the number, whoever builds the response.
A `level` that doesn't match its `score` is a backend bug (500). `tests/test_trait_levels.py` fails if a
trait field in any response isn't a `Trait`. New traits go in `TRAIT_FIELDS` so the test covers them.

| Score | `level` |
|---|---|
| 0 | `none` |
| above 0, below 0.5 | `low` |
| 0.5 to below 0.8 | `medium` |
| 0.8 to 1 | `high` |

The data uses 0, 0.33, 0.67 and 1, one value per band. The cutoffs are placeholders (`LOW_BELOW`,
`MEDIUM_BELOW`).

### Rules the loader enforces
Any violation stops startup with a `ConfigError` that names the file and line.
- Ranges: `abs_min ≤ opt_min ≤ opt_max ≤ abs_max`.
- `root_depth_m` in `(0, 5]`.
- Trait columns: a number from 0 to 1.
- `sources`: at least one citation, separated by `;`. Quote the cell if a citation contains a comma.

## Current data (5 crops)
See `data/ecocrop_subset.csv`. Every row is `verified=true`: the **temperature, rainfall and pH
ranges come from FAO EcoCrop** (`scripts/import_ecocrop.py`, see `docs/sources/ecocrop.md`). Also:
- **Root depth** comes from FAO-56 (Allen et al. 1998), Table 22, upper value of the range:
  rice 1.0, beans 0.9, maize 1.7, sorghum 2.0, cowpea 1.0 m.
- **Cover crop, forage, nutrition, mycorrhizal and nitrogen demand** are a **team estimate**, and each
  row's `sources` says so. #24 replaces them with cited values. Main judgements to check: rice is
  0.33 (low) mycorrhizal (flooded paddies suppress the fungi), legumes are 0.33 (low) nitrogen demand,
  and only cowpea is a cover crop.
- **Market notes** are generic. Confirm them with a local source before the demo.

## API impact (in the contract)
`Crop` in `GET /crops` gains the same fields with the same names, all required:
`root_depth_m: number`, `is_cover_crop: boolean`, `forage_value`, `nutrition_density`,
`mycorrhizal_affinity`, `nitrogen_demand` (`TraitValue`: `{level, score}`), `market_note: string`,
`sources: string[]`, plus the new `TraitValue` schema.
See `docs/examples/crops.json` for the response.

## Design decisions (answered 2026-11-14 by marceconejo)
1. **Levels vs numbers: both.** 0..1 scores in the data and the engine. The API sends the word and the
   score together, so the frontend can show the number on hover (see "Trait scores" above).
2. **`nitrogen_demand`: keep.** Rule #25 needs it to spot heavy feeders.
3. **File name: keep** `data/ecocrop_subset.csv`.
4. **Long-cycle crops** (cassava, plantain): **left out** of #24 for now. The season model plants one
   crop per season (see `decisions.md`).
