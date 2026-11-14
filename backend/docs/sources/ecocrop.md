# FAO EcoCrop: crop tolerance ranges

| Field | Value |
|---|---|
| **Used for** | Crop temperature, rainfall and pH ranges (`CropSource`) |
| **Adapter** | `app/integrations/ecocrop.py` |
| **Data** | `data/ecocrop_subset.csv` (versioned, no network needed) |
| **Status** | ⚠️ Values approximate: every row is `verified=false` |

## What EcoCrop gives
For each crop: absolute and optimal ranges for temperature (°C), rainfall (mm over the growing
period), soil pH, plus crop cycle length (days), soil depth, texture, and more. The original FAO
database web page is no longer reliably online. Copies circulate as the `ECOcrops` dataset in the
R package `dismo` (function `ecocrop`) and in research datasets.

## CSV columns
`id, name, scientific_name, family, is_legume, cycle_days,
temp_{abs_min,opt_min,opt_max,abs_max}, rain_{…}, ph_{…}, root_depth_m, is_cover_crop,
forage_value, nutrition_density, mycorrhizal_affinity, nitrogen_demand, market_note, sources, verified`

Only the ranges and `cycle_days` come from EcoCrop. Meaning, allowed values and sources of every
column: [`../crop-schema.md`](../crop-schema.md).

Rule: `abs_min ≤ opt_min ≤ opt_max ≤ abs_max`. The loader rejects rows that break it.

## To do
1. Get an authoritative copy of EcoCrop (e.g. `dismo` ECOcrops data) and check every row's values.
2. Set `verified=true` per row once checked, and note the source in this file.
3. Add the crops the team picks for the pilot region (cassava, sweet potato, …). Crops with a cycle
   much longer than one season need a different rotation model (see decisions.md).
4. Optional: per-crop soil moisture and texture preferences.
