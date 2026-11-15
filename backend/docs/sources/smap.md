# NASA SMAP L4: root-zone soil moisture

| Field | Value |
|---|---|
| **Used for** | Soil moisture in scoring (`soil_moisture` variable), month by month |
| **Adapter** | `app/integrations/smap.py` → `MeasuredSoil` (`app/integrations/measured_soil.py`, with OpenLandMap pH) |
| **Dataset** | `NASA/SMAP/SPL4SMGP/008` on Google Earth Engine: SMAP L4 Global 3-hourly 9 km surface and root zone soil moisture |
| **Bands** | `sm_rootzone`: volumetric water content, **m³/m³**, root zone **0–100 cm** (range 0–0.9). `sm_rootzone_wetness`: relative saturation of the same layer, **0 (dry) to 1 (saturated)**, against the model's own porosity |
| **Coverage** | Global land, 2015-03-31 to near real time (checked 2026-11-15: last image 2026-11-10) |
| **Resolution** | 9 km EASE-Grid (catalog pixel size ~11 km); 3-hourly (hh:30 UTC) |
| **License** | Public domain per the Earth Engine catalog; NSIDC asks users to cite the data set: Reichle et al., SMAP L4 Global 3-hourly 9 km EASE-Grid Surface and Root Zone Soil Moisture Geophysical Data, Version 8, NSIDC DAAC, doi:10.5067/T5RUATAQREF8 |
| **Fixtures** | `tests/fixtures/smap/monthly_alajuela.json` (lat 10.0, lon −84.2) and `monthly_san_carlos.json` (lat 11.0, lon −84.6), fetched 2026-11-15 with the adapter's own request |
| **Access** | Earth Engine project (`GEE_PROJECT_ID`) + `earthengine authenticate`, same as OpenLandMap |

## What the adapter asks for
One Earth Engine request per location, returning 12 numbers:
- `sm_rootzone`, **2020–2024**, **one reading per day** (13:30 UTC = 07:30 in Costa Rica);
- the **mean of the pixels within 15 km** of the point, per calendar month.

Why this shape:
- The full 3-hourly series (~14,600 images for 5 years) exceeds Earth Engine's user memory limit.
  One reading per day (8× fewer) with each image clipped to the area works in ~30 s.
- Images are at hh:30 UTC: a filter on 12:00 matches nothing (an empty collection gives no values).
- One pixel can be masked (open water); the mean over 15 km avoids an empty answer near lakes and
  wetlands (San Carlos is close to Lake Nicaragua and the Río Frío wetlands).

The answer is cached forever (historical means don't change), like the OpenLandMap maps, so
`cached` mode never calls Earth Engine. A month without a value is an error (`source_bad_data`),
never a guess.

## How scoring uses it
- `SoilConditions.moisture_monthly_m3m3` holds the 12 means; `moisture_m3m3` is their yearly mean.
- Each season (rotations) or sowing month (planting windows) is scored on the **mean of its own
  months**, like rainfall. Moisture is therefore a month-varying variable and can shape planting
  windows.
- Moisture is compared with `GENERIC_SOIL_MOISTURE`, **dry side only**: 0 at or below 0.10 m³/m³,
  1 from 0.20, no upper limit. SMAP's absolute m³/m³ depend on its model's soil, so "too wet" is not
  judged from them (agro-logic review 2026-11-15).
- **Waterlogging** uses the wetness band instead, only for crops EcoCrop says need good drainage
  (`needs_good_drainage`; all but rice): the cycle's mean wetness lowers the score gradually from
  0.80 to −15 % at 0.95, with a warning from 0.85. Never a veto, and it never removes a month from
  a planting window (it flags it). Placeholders (decisions.md).

## Real values (2020–2024 monthly means)

Moisture (m³/m³):
| Point | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| San Carlos (11.0, −84.6) | 0.32 | 0.29 | 0.24 | 0.21 | 0.21 | 0.26 | 0.33 | 0.36 | 0.35 | 0.36 | 0.36 | 0.35 |
| Alajuela (10.0, −84.2) | 0.45 | 0.41 | 0.38 | 0.38 | 0.43 | 0.49 | 0.50 | 0.51 | 0.51 | 0.52 | 0.51 | 0.48 |

Wetness (relative saturation, 0–1):

| Point | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| San Carlos | 0.76 | 0.68 | 0.58 | 0.51 | 0.49 | 0.63 | 0.77 | 0.84 | 0.84 | 0.85 | 0.87 | 0.83 |
| Alajuela | 0.83 | 0.76 | 0.71 | 0.70 | 0.78 | 0.89 | 0.93 | 0.93 | 0.94 | 0.95 | 0.94 | 0.88 |

The soil dries and wets **1–2 months after the rain** (May is rainy but the soil is still at its
driest; December is dry but the soil is still wet). That residual moisture is what late sowings
(e.g. Zona Norte beans in Nov–Dec) rely on, and it was invisible with rainfall alone.

## Limits
- SMAP L4 is **satellite data assimilated into a land model**, not a field measurement.
- ~9 km pixels and a 15 km mean: it describes the area, not one field.
- Monthly means of 2020–2024: no year-to-year variation (see #34).
