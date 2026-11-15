# OpenLandMap soil properties (via Google Earth Engine)

| Field | Value |
|---|---|
| **Used for** | Soil properties by depth for suitability and rotation choices (`SoilProfileSource`) |
| **Adapter** | `app/integrations/openlandmap.py` → `services.get_soil_data()` |
| **Fixtures** | `tests/fixtures/openlandmap/soil_san_jose.json` (lat 9.93, lon −84.08) and `soil_pacific_ocean.json` (lat 9.5, lon −86.0, every pixel masked). Both fetched 2026-11-14 with the same request the adapter makes |
| **Status** | ⚙️ Adapter + `services.get_soil_data()`, wired in `build_sources()` (`Sources.soil_profile`, `MockSoilProfile` in mock mode); served by `GET /soil`. Not used for scoring yet: `Sources.soil` (pH + moisture for suitability) is still `MockSoil` |

## Access
- Google Earth Engine Python API (`earthengine-api`), Cloud project `advance-topic-243700` (default in `app/settings.py`; `GEE_PROJECT_ID` in `.env` overrides it).
- Auth, never interactive during a request:
  - Local: run `earthengine authenticate` once (or `gcloud auth application-default login`).
    `ee.Initialize(project=…)` picks up those stored credentials.
  - Deployment: a service account registered for Earth Engine. Point `GEE_SERVICE_ACCOUNT_KEY_FILE`
    at its JSON key file. **Never commit the key file.**
- Initialized once per process, on the first uncached request (not at startup, not per request).
- One request per location: all 7 assets × 3 depths in one `ee.Image.cat(...).reduceRegion(first)`,
  ~3–4 s cold. Each 250 m pixel is cached forever (the maps are static), in every mode, live included.
- Quota: Earth Engine non-commercial / research use. No per-call key quota like OpenTopography.
- License: **CC-BY-SA 4.0**. Show the credit line (`ATTRIBUTION`, returned as `attribution`).
  Cite Hengl (2018) and Hengl & Gupta (2019), doi:10.5281/zenodo.1475457 and related Zenodo records.

## Datasets, bands and units (checked against Earth Engine on 2026-11-14)
All 7 assets have the same bands `b0, b10, b30, b60, b100, b200` (depth in cm), are stored as
uint8 and share one grid: EPSG:4326, 1/480° pixels (~232 m, "250 m" nominal), top edge 87.37° N.
We read `b0`, `b10`, `b30`. The scale comes from the catalog (`gee:scale`, `gee:units`) and the
dataset titles. Note that the catalog's `gee:scale` is a divisor for pH but a multiplier for carbon
and bulk density. The real values at the fixture point confirm the reading below.

| Property (our name) | Asset (`OpenLandMap/SOL/…`) | Stored as | Conversion | San José 0 cm |
|---|---|---|---|---|
| `ph` | `SOL_PH-H2O_USDA-4C1A2A_M/v02` | pH × 10 | ÷ 10 | 66 → 6.6 |
| `organic_carbon_g_kg` | `SOL_ORGANIC-CARBON_USDA-6A1C_M/v02` | "× 5 g/kg" | × 5 → g/kg | 2 → 10 g/kg |
| `clay_pct` | `SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02` | % (kg/kg) | none | 38 % |
| `sand_pct` | `SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02` | % (kg/kg) | none | 34 % |
| `bulk_density_kg_m3` | `SOL_BULKDENS-FINEEARTH_USDA-4A1H_M/v02` | 10 × kg/m³ | × 10 | 127 → 1270 kg/m³ |
| `field_capacity_m3m3` | `SOL_WATERCONTENT-33KPA_USDA-4B1C_M/v01` | volumetric % at 33 kPa | ÷ 100 → m³/m³ | 34 → 0.34 |
| `texture_class` | `SOL_TEXTURE-CLASS_USDA-TT_M/v02` | class code 1–12 | name lookup | 4 → clay loam |
| `silt_pct` | derived | — | 100 − clay − sand | 28 % |

- Texture codes (from the asset's `b*_class_names`): 1 Cl clay, 2 SiCl silty clay, 3 SaCl sandy clay,
  4 ClLo clay loam, 5 SiClLo silty clay loam, 6 SaClLo sandy clay loam, 7 Lo loam, 8 SiLo silt loam,
  9 SaLo sandy loam, 10 Si silt, 11 LoSa loamy sand, 12 Sa sand.
- Masked pixels (sea, lakes, ice, no prediction) come back as `null` and are returned as `None`.
- Values outside physical limits, unknown texture codes or missing bands → `source_bad_data`.

## Coverage and resolution
- Global land, 250 m nominal. Costa Rica is covered (the fixture point is inside the pilot area).
- Values are model predictions (machine learning on soil profiles plus covariates), not
  measurements. They describe a ~5 ha pixel, not one field.
- The data has no time dimension: one release, representing roughly 1950–2017.

## Gotchas
- Carbon is stored in steps of 5 g/kg, so 10 g/kg means 7.5–12.5 g/kg. Density is stored in steps of 10 kg/m³.
- Clay and sand are predicted by separate models, so they can add up to more than 100 %. Then
  `silt_pct` is `None` rather than negative.
- The point is snapped to its pixel centre, so nearby clicks share a cache entry. Sampling uses
  the native grid (`crsTransform`), so there is no resampling between neighbouring pixels.
- Importing `ee` takes ~0.6 s, so it's imported only when a request is actually made.
