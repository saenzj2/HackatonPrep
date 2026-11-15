# Crop candidates for later (#24)

> **Not in the app.** The MVP keeps 5 crops (rice, beans, maize, sorghum, cowpea). This is a
> shortlist to discuss with the team if time allows. Every candidate needs a local check
> (MAG / INTA) before it's added.

## How the list was made (2026-11-15)
All 2568 crops in the EcoCrop Parquet (`docs/sources/ecocrop.md`) were run through our own
planting-window code (`app/domain/planting_windows.py`) with the cached NASA POWER climate for
Los Chiles (lat 11.0, lon −84.6):
- annual crops used as cereals, pulses, vegetables, roots/tubers or cover crops;
- shortest cycle (`gmin`) between 30 and 120 days, so it fits one season;
- only the month-varying variables (temperature, heat, frost, rainfall). Soil is still mock.

**51 crops** have at least one planting window. Many are not realistic here (barley, rye, oats,
lentil, potato, onion): the screen sees temperature and rain, not humidity, disease pressure, soil
or markets. The shortlist below is hand-picked from those 51 for what it adds to the rotation
comparison. Reasons marked *(check)* are judgement, not verified.

## Shortlist
| Crop | EcoCrop code | Family | Cycle (d, shortest) | Los Chiles window (sow) | What it adds |
|---|---|---|---|---|---|
| **Sunn hemp** (*Crotalaria juncea*) | 801 | Fabaceae | 60 | Aug–Oct | Fast cover crop and green manure; a legume that isn't a grain crop |
| **Squash / ayote** (*Cucurbita moschata*) | 820 | Cucurbitaceae | 80 | Jul–Sep | New family; part of the maize–bean–squash milpa |
| **Peanut** (*Arachis hypogaea*) | 2199 | Fabaceae | 90 | May, Jul–Oct | Legume cash crop, nutritious |
| **Soybean** (*Glycine max*) | 1150 | Fabaceae | 75 | Aug–Sep | High-protein legume |
| **Hyacinth bean / lablab** (*Lablab purpureus*) | 1311 | Fabaceae | 70 | Aug–Sep | Food legume and cover crop |
| **Hot pepper** (*Capsicum chinense*) | 4178 | Solanaceae | 120 | Jun–Oct | New family with market value |
| **Quinoa** (*Chenopodium quinoa*) | 2509 | Amaranthaceae (EcoCrop: Chenopodiaceae) | 90 | May–Oct | **Mycorrhizal non-host**: makes the `fungi_break` rule testable with real data. Humid-lowland disease risk *(check)* |
| **Rapeseed / canola** (*Brassica napus*) | 549 | Brassicaceae | 85 | May–Oct | **Mycorrhizal non-host** (Brassicaceae). Fit for a humid lowland *(check)* |

## Worth checking, but not found by the screen
- **Amaranth** (*Amaranthus* spp.): nutritious non-host, but didn't pass the filters (missing
  ranges or cycle in EcoCrop). Needs values from another source.
- **Jack bean** (*Canavalia ensiformis*) and **velvet bean** (*Mucuna pruriens*): classic Central
  American cover crops, but EcoCrop doesn't list them as annual with a cycle ≤ 120 days. They may need
  a longer-season model.
- **Sweet potato**: listed as a root crop but not as annual in EcoCrop.
- **Rainfed (upland) rice**: EcoCrop only has flooded-rice ranges (see `docs/sources/ecocrop.md`).

## To add one
1. Add a row to `data/ecocrop_subset.csv` with our own columns (family, legume, cycle, root depth,
   traits, market note, sources).
2. Add its `ecoportcode` to `ECOPORT_CODES` in `scripts/import_ecocrop.py` and rerun the import with
   `--write-fixture` (`docs/sources/ecocrop.md`, "Refresh").
3. To use it in the default recommendations, add its id to `crops` in `config/mvp.yaml` (team
   decision, `decisions.md` entry).
