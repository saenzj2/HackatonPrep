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
| [API contract](backend/docs/api-contract.yaml) | Frontend/backend agreement, currently `0.2.0-draft` |
| [San Carlos pilot baseline](docs/pilot-baseline/README.md) | Selected example location, six research images, provenance, limitations and next steps |

Challenge details below summarize the official-page text supplied by the team. The official
URL was located in search, but a complete live-page fetch timed out during documentation.
The roster, venue, timetable and local rubric were supplied by the team, including event images;
they have not been independently confirmed with the organizer. The dataset catalog below lists
discovery entry points, not proof of acquisition or suitability. The separate San Carlos baseline
records the sources actually explored and their checked redistribution terms.

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

Repository snapshot for this context: **14 November 2026**, inspected at `1992e21`.
These are source/configuration observations, not fresh runtime or scientific validation results.
The selected research/demo example is **San Carlos, Costa Rica**, at **10.999930, -84.601590**
(latitude, longitude). This selection does not establish a farm boundary or finalize the configured
pilot scope. See the [visual baseline and provenance](docs/pilot-baseline/README.md).

| Topic | Current evidence | Still provisional or limited |
|---|---|---|
| Pilot region | San Carlos example selected for research; config still says `TBD (placeholder: Costa Rica)` | Config bounds remain Costa Rica-wide; no farm ownership or surveyed boundary established |
| Crops | Config selects `rice`, `beans`, `maize` | Team still needs to confirm the final 3–5 crops; catalog values are marked `verified=false` |
| Variables | Temperature, rainfall, soil pH, soil moisture, heat and frost | Heat/frost use monthly summaries, not daily event counts; no measured soil-health or water-saving improvement |
| Priorities | Defaults: water 0.4, soil 0.3, climate 0.3; request can override | Defaults are not individual farmer preferences |
| Seasons | `primera` May–August; `postrera` September–November | Dry season is fallow in v0; regional/irrigation fit needs review |
| Output | Ranked rotations, optional `current_rotation`, score deltas, benefits, risks, data gaps and evidence | Baseline requires farmer input; the API does not invent current practice or guarantee exactly three strategies |
| Climate | POWER monthly normals feed conditions/ranking in live/cached mode; daily DataFrame adapter also exists | Daily data is not wired into recommendation services; no live pilot call verified in this documentation task |
| Soil | `MockSoil` in **every** mode | SoilGrids SOC was explored externally, not integrated; it does not replace mocked pH/moisture |
| Crop source | Local EcoCrop subset CSV | Unverified trait values must not be presented as validated agronomy |
| Ranking | `suitability-v1`, cyclic rotation adjustments including same-family penalty | Penalties and legume bonus are placeholders, not calibrated agronomic impacts |
| Frontend | README leaves same-repo versus separate-repo location open | No completed dashboard is asserted here |

The scope principle remains **one region, a few crops, a few variables and one clear
recommendation**. Do not change config, scoring constants or the API contract through this
context document. Follow the existing contract-first workflow and decision-log rules.

### Farmer-first map direction (not implemented here)

The user favors a map flow: open a recognizable example, select a rectangular area, inspect
available evidence, optionally enter existing crops/current practice, set priorities, then compare
explained options. A farmer without a current crop must also be able to explore the evidence.
This is a design direction, not an implemented dashboard or a finalized polygon-analysis contract.
Show source/provider, date or period, resolution, uncertainty and mock status beside each layer/result.
The existing API accepts a **point**, not a rectangle or polygon; an explicitly labeled representative
point could bridge a future selection UI to it, but point-selection rules still need agreement.
Do not describe the response as an area average or field-level measurement.

#### Two entry paths, one evidence standard

| Farmer situation | Intended experience | Current API boundary |
|---|---|---|
| No current crop or no baseline supplied | Inspect location evidence and compare supported candidate crops/rotations without inventing current practice | Omit `current_rotation`; omit `crops` to use configured candidates, or supply supported catalog IDs. No baseline score delta is available. |
| Existing crop supplied by the farmer | Inspect relevant data and recommendations for that crop; offer an alternative only when traits, local conditions and rotation logic support it | `current_rotation` is a sequence with one supported crop per configured season, not a generic single-current-crop field. A new field or different crop-cycle model requires contract-first agreement. |

An unknown or unsupported crop must remain an explicit gap, not be silently replaced. If evidence
cannot justify a recommendation or alternative, explain the missing evidence instead of inventing
an option. Current heuristic rankings and unverified catalog traits do not establish agronomic validity.
This is the intended evidence standard, not a claim that the current API already filters all unsupported
agronomic conclusions. Single-crop advice and changed response behavior need separately agreed
[contract](backend/docs/api-contract.yaml) changes, implementation and tests.

**Hypothetical example, not exclusive scope:** a farmer reports pineapple at San Carlos. This is
one possible walkthrough, not the only supported user situation or a verified crop identification.
The images show agricultural-looking patterns, not confirmed pineapple. Pineapple is not among
the configured crops (`rice`, `beans`, `maize`). Validate actual crops and the local seasonal calendar
before adapting the model: the default dry-season fallow assumption may not fit this northern site.
Water, soil and climate remain farmer-selected priorities; defaults are examples, not elicited needs.

### Cache-first direction and quota boundaries

**Prefer reuse of suitable cached evidence, not default live calls.** This is a proposed operating
policy, not a new `data_mode` or an implemented default. Current configuration remains `mock`, with
an environment override; `cached` is offline-only, whereas `live` fetches on every request and only
falls back to a saved copy after a source error. Cache-first read-through behavior, freshness rules
and quota accounting are not implemented by this documentation.

| Situation | Intended policy / current limitation |
|---|---|
| Valid matching cache hit | Reuse without a live call; show provider, location/parameters, observation period and retrieval date. Current cache stores `params`, `fetched_at` and raw data, but does not enforce freshness. |
| Stale cached evidence | Label age and scientific limits; use only if suitable for the question. Do not silently refresh or imply historical evidence is current. Agree on source-specific freshness rules before implementation. |
| Miss, unreadable entry or empty cache | In `cached`, return the existing `cache_miss` error (503), with no network request. Do not silently switch to live or mock; explain that evidence is unavailable. |
| Explicit live acquisition/refresh allowed | First agree on location, source, credentials and budget; fetch only when configured/authorized and cache validated results. A cache miss alone is not authorization. |
| Live disabled, required key missing, or quota exhausted | Make no new external calls under the proposed policy. Use suitable labeled cache if available, otherwise report the gap; partial response behavior needs contract agreement. Current shared cache has no quota/key preflight. |
| Demo | Prepare only agreed requests within budget, verify cache completeness, then use `cached`; rehearse a miss as well as a hit. Soil mock status must remain visible. |

The user's 50-calls/day concern appears to match the **OpenTopography Point Elevation API** in
[open PR #66](https://github.com/saenzj2/HackatonPrep/pull/66), not an established merged backend
source or a NASA POWER quota. The [provider's developer page](https://opentopography.org/developers/),
checked 14 November 2026, lists **50 calls per 24 hours for non-academic free Point Elevation keys**
and 250 for academic keys; limits depend on endpoint and plan. Verify the actual account entitlement
before acquisition, and do not share or publicly embed keys. PR #66 describes five elevation requests
for a new location; that is an in-flight design estimate, not a universal cost per recommendation.
Cache keys, repeated selections and failed/retried requests must be included in any later budget design.

See [issue #67](https://github.com/saenzj2/HackatonPrep/issues/67) for this documentation follow-up.
This page changes no code, configuration, contract, API quota control or integration.

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

- Use the [San Carlos baseline](docs/pilot-baseline/README.md) as the selected visual example;
  no farmer or real farm is available; label the scenario hypothetical and seek expert validation later.
- Agree on the rectangle-selection/representative-point handoff and frontend contract; reuse the
  existing optional current-rotation comparison rather than treating it as missing.
- Verify crop traits and choose a real soil strategy before claiming agronomic validity. Keep the
  externally explored SOC map distinct from backend mock pH/moisture.
- Reuse suitable cached NASA POWER evidence; acquire only missing agreed pilot-point data within budget,
  then verify effective mode/source labels before the demo;
  existing example responses describe Alajuela, not this San Carlos point.
- Select only evidence layers that help the farmer, with dates, attribution and limitations visible;
  FTW predictions are incomplete here and cannot silently define the selected farm.
- Confirm organizer timetable changes, submission requirements and any deadlines not provided here.

Use the [tracker](https://github.com/users/saenzj2/projects/1/views/5) for work ownership and
the [decision log](backend/docs/decisions.md) for accepted technical decisions. This context page
does not assign work, authorize new integrations or finalize the provisional MVP.
