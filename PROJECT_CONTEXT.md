# Guardians of the Harvest: shared project context

**Start here for the challenge, people, data candidates and local event plan.** This is a
context reference, not a new product specification or a claim that every dataset is integrated.
For running the backend, use the [README](README.md); for contributor rules, read [AGENTS.md](AGENTS.md).

## Essential links and source boundaries

| Reference | Purpose |
|---|---|
| [Official challenge](https://www.spaceappschallenge.org/2026/challenges/field-shift-adapting-farms-with-nasa-data/) | Field Shift: Adapting Farms with NASA Data, NASA Space Apps Challenge 2026 |
| [Repository](https://github.com/saenzj2/HackatonPrep) | Shared code and versioned documentation |
| [Project tracker](https://github.com/users/saenzj2/projects/1/views/5) | Team task coordination; consult it for current assignments |
| [MVP configuration](backend/config/mvp.yaml) | Actual configured region, crops, variables, seasons and data mode |
| [Decision log](backend/docs/decisions.md) | Recorded technical choices and limitations |
| [API contract](backend/docs/api-contract.yaml) | Frontend/backend agreement, currently draft v0 per the decision log |

Challenge details below summarize the official-page text supplied by the team. The official
URL was located in search, but a complete live-page fetch timed out during documentation.
The roster, venue, timetable and local rubric were supplied by the team, including event images;
they have not been independently confirmed with the organizer. Dataset links are discovery
entry points, not proof of downloaded data, licensing review or pilot-region suitability.

## Team

**Guardians of the Harvest**

| Participant | Confirmed designation |
|---|---|
| Anny Gutiérrez | Owner (as supplied) |
| Carlo Cespedes | Team member |
| Jeffrie Saenz | Team member |
| Andres Calvo Vargas | Team member |
| Marcela Conejo Araya | Team member |
| David Molina Shvidchenco | Team member |

No engineering, presentation or domain-expert roles are assigned by this document.

## What the challenge asks, and what remains a choice

The challenge asks for decision support that combines NASA Earth observations, local soil
information, crop characteristics and farmer priorities to explore crop rotations under
changing weather and resource constraints. Soil condition, water conservation and resilience
are the intended outcomes; a suitability score alone is not proof of those outcomes.

| Challenge direction | Implementation implication |
|---|---|
| Help farmers explore rotations | Compare understandable options, not just individual crops |
| Use environmental evidence and farmer priorities | Make sources, relevant conditions and priority effects visible |
| Explain benefits, risks and uncertainty | Distinguish observations, estimates, assumptions and missing information |
| Support farmer judgment | Do not present the ranking as an agronomic prescription or guaranteed yield |

The supplied brief **suggests**, rather than mandates, comparing three strategies including
the current-practice baseline. That is one useful demo format, not a requirement for exactly
three results. A baseline still needs the farmer's actual practice; do not invent it.
The dataset catalog is a set of possibilities, not an instruction to integrate every source.

## Current implementation versus provisional scope

Repository snapshot for this context: **14 November 2026**. These are documented/configured
facts, not fresh runtime or scientific validation results.

| Topic | Current evidence | Still provisional or limited |
|---|---|---|
| Pilot region | Config name is `TBD (placeholder: Costa Rica)` with a bounding box | Costa Rica is not a finalized pilot selection |
| Crops | Config selects `rice`, `beans`, `maize` | Team still needs to confirm the final 3–5 crops; catalog values are marked `verified=false` |
| Variables | Temperature, rainfall, soil pH and soil moisture | No measured improvement in soil health or water savings is established |
| Priorities | Defaults: water 0.4, soil 0.3, climate 0.3; request can override | Defaults are not individual farmer preferences |
| Seasons | `primera` May–August; `postrera` September–November | Dry season is fallow in v0; regional/irrigation fit needs review |
| Output | `top_n: 5` in config | Does not establish a three-strategy baseline comparison |
| Climate | NASA POWER adapter for live/cached; mock climate in mock mode | Existing adapter does not imply a live call was verified in this documentation task |
| Soil | `MockSoil` in **every** mode | No real soil integration selected; SMAP/SoilGrids are candidates only |
| Crop source | Local EcoCrop subset CSV | Unverified trait values must not be presented as validated agronomy |
| Ranking | Explainable v0 scoring and cyclic rotation adjustments | Monoculture penalty and legume bonus are placeholders, not calibrated impacts |
| Frontend | README leaves same-repo versus separate-repo location open | No completed dashboard is asserted here |

The scope principle remains **one region, a few crops, a few variables and one clear
recommendation**. Do not change config, scoring constants or the API contract through this
context document. Follow the existing contract-first workflow and decision-log rules.

### Demo honesty

- Default `data_mode: mock` means deterministic synthetic climate/soil inputs; label them clearly.
- `live` uses the POWER adapter; `cached` avoids network requests. Soil is still mock in both.
- The environment setting can override the configured data mode. Confirm effective mode before presenting.
- Explain source dates, resolution, missing values and heuristic limitations. Historical climate normals
  are not a weather forecast, and coarse pixels do not establish a field-level measurement.
- Do not claim verified resilience, yield, profit or water savings from the current ranking.

## Dataset and resource inventory

These are **candidates from the supplied challenge context**, not an approved acquisition plan.
Coverage labels are screening guidance: verify the exact product, period, units, access terms,
resolution and pilot overlap before use. A globally available mission does not guarantee a usable
observation over a particular field or date. See [source onboarding](README.md#adding-a-data-source-by-hand).

### NASA and associated Earth-observation resources

| Resource / official entry point | Possible contribution | Coverage and caution |
|---|---|---|
| [SMAP](https://smap.jpl.nasa.gov/) | Soil moisture | Broad land coverage; coarse moisture is not local soil pH or a soil-health assessment |
| [GPM / IMERG](https://gpm.nasa.gov/data/imerg) | Rainfall patterns | Broad coverage; verify product footprint and local rainfall uncertainty |
| [Landsat](https://www.usgs.gov/landsat-missions) | Vegetation, land cover, surface conditions | Global land archive; clouds and revisit timing matter |
| [MODIS](https://modis.gsfc.nasa.gov/) / [VIIRS](https://www.earthdata.nasa.gov/data/instruments/viirs) | Vegetation and environmental indicators | Broad coverage; often too coarse to resolve a small farm |
| [NASA POWER](https://power.larc.nasa.gov/) | Temperature and rainfall context | Global gridded climate; existing backend source, not field weather measurements |
| [SRTM](https://www.usgs.gov/centers/eros/science/usgs-eros-archive-digital-elevation-shuttle-radar-topography-mission-srtm-1) | Elevation and terrain | Near-global land, not polar-global; terrain alone does not determine crop fit |
| [ECOSTRESS](https://ecostress.jpl.nasa.gov/) | Thermal/water-stress context | ISS sampling; confirm actual scene availability and quality over the pilot |
| [GEDI](https://gedi.umd.edu/) | Vegetation structure | ISS lidar footprints, not continuous field coverage or a crop-trait catalog |
| [GLDAS](https://ldas.gsfc.nasa.gov/gldas) / [NLDAS](https://ldas.gsfc.nasa.gov/nldas) | Modeled land-surface water/energy context | GLDAS is global; NLDAS is North American, not a default Costa Rica source |
| [GRACE / GRACE-FO](https://gracefo.jpl.nasa.gov/) | Regional water-storage change | Very coarse regional signal, not direct farm groundwater measurements |

### Partner and complementary global resources

| Resource / official entry point | Possible contribution | Coverage and caution |
|---|---|---|
| [Sentinel-2 (ESA)](https://www.esa.int/Applications/Observing_the_Earth/Copernicus/Sentinel-2) | Vegetation and land cover | Broad land coverage; clouds and product quality require checks; not NASA |
| [ERA5 (ECMWF/Copernicus)](https://www.ecmwf.int/en/forecasts/dataset/ecmwf-reanalysis-v5) | Historical climate context | Global reanalysis, not local observations or a forecast; not NASA |
| [GAEZ (FAO/IIASA)](https://gaez.fao.org/) | Agro-ecological suitability context | Global screening; scenario assumptions and scale need review |
| [USDA Ag Data Commons](https://agdatacommons.nal.usda.gov/) | Agricultural research datasets | Repository coverage varies per dataset; no blanket Costa Rica coverage |

### Primarily U.S. or coverage-specific resources

Do **not** treat these as Costa Rica-ready just because the challenge lists them.

| Resource / official entry point | Possible contribution | Coverage gate |
|---|---|---|
| [Web Soil Survey](https://websoilsurvey.nrcs.usda.gov/) | Soil survey properties | U.S. survey system; verify geography before selection |
| [SSURGO / STATSGO2](https://www.nrcs.usda.gov/resources/data-and-reports/soil-geographic-databases) | Soil mapping | U.S. products, not a Costa Rica soil source |
| [Cropland Data Layer (CDL)](https://www.nass.usda.gov/Research_and_Science/Cropland/SARS1a.php) | Crop/land-cover history | U.S. crop mapping, not Costa Rica |
| [PRISM](https://prism.oregonstate.edu/) | Climate grids | U.S.-focused; confirm particular product coverage |
| [NAIP](https://www.fsa.usda.gov/resources/programs/aerial-photography) | Aerial imagery | U.S. program, not global farm imagery |
| [NLCD](https://www.usgs.gov/centers/eros/science/national-land-cover-database) | Land cover | U.S. database; no implied Costa Rica coverage |
| [CoCoRaHS](https://www.cocorahs.org/) | Volunteer precipitation observations | Station-network availability varies; confirm local stations and completeness |
| [NWIS](https://waterdata.usgs.gov/nwis) | Streamflow and water observations | USGS monitoring network; no assumed Costa Rica stations |
| [USDA Market News](https://www.ams.usda.gov/market-news) | Market/pricing context | Market and commodity coverage varies; not Costa Rican farm-gate prices |
| [USDA QuickStats](https://quickstats.nass.usda.gov/) | Agricultural statistics | U.S. statistics, not a Costa Rica crop census |
| [OpenET](https://openetdata.org/) | Evapotranspiration estimates | U.S.-focused service; verify current footprint, do not assume Costa Rica |
| [LANDFIRE](https://landfire.gov/) | Vegetation/fire context | U.S.-focused products; confirm geography and relevance |

Before accepting a source, save a real fixture and document variables, **units**, spatial/temporal
resolution, regional coverage and license under `backend/docs/sources/`, as required by the repo.
Prioritize a small usable evidence chain over integrating the whole catalog.

## Local event: 14–15 November 2026

**Venue supplied:** Universidad Fidélitas, San Pedro. Times below reproduce the supplied
local-event images in 24-hour format (Costa Rica local time). Confirm organizer updates at the venue.
They are not a NASA-wide schedule or submission-deadline specification.

| 14 November | Activity | 15 November | Activity |
|---|---|---|---|
| 08:00–09:00 | Reception | 08:00–09:00 | Development |
| 09:00–10:00 | Welcome | 09:00–10:00 | Snack |
| 10:00–11:00 | Introduction | 10:00–12:00 | Development |
| 11:00–12:00 | Development | 12:00–13:00 | Lunch |
| 12:00–13:00 | Lunch | 13:00–15:00 | Development |
| 13:00–15:00 | Development | 15:00–16:00 | Coffee break |
| 15:30–16:30 | Coffee break | 16:00–17:00 | Development |
| 16:00–17:00 | Mentoring | 17:00–19:00 | Project exhibition |
| 17:00–19:00 | Development | — | — |

The 14 November source has an unassigned 15:00–15:30 interval and overlapping coffee/mentoring
from 16:00–16:30. These are preserved, not silently corrected; ask the organizer if coordination depends on them.

### Supplied local judging rubric

| Criterion | Points |
|---|---:|
| Impact | 30 |
| Creativity | 20 |
| Feasibility | 20 |
| MVP | 20 |
| Presentation | 10 |
| **Total** | **100** |

This is the local rubric supplied by the team, not a claim about global NASA judging rules.
A useful presentation connects the farmer problem to a working comparison, explains NASA evidence,
shows limits honestly and leaves the decision with the farmer.

## Open decisions and next handoff

- Confirm the pilot location and crops; keep tentative choices explicitly tentative until accepted.
- Agree on the frontend contract and baseline comparison; do not infer assignments from the roster.
- Verify crop traits and choose a real soil strategy before claiming agronomic validity.
- Select only the data products that improve the demo within the time available.
- Confirm organizer timetable changes, submission requirements and any deadlines not provided here.

Use the [tracker](https://github.com/users/saenzj2/projects/1/views/5) for work ownership and
the [decision log](backend/docs/decisions.md) for accepted technical decisions. This context page
does not assign work, authorize new integrations or finalize the provisional MVP.
