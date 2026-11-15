# Follow-up: tighter ranges for permanent crops (and potato, onion)

> **Status (2026-11-15):** proposals only, nothing applied. Scoring changes need the engine
> owner's OK and a `decisions.md` entry. Context: `decisions.md` entries "Permanent crops" and
> "Heat and frost now use the mean daily max / min".

## Problem
After the heat fix, `GET /permanent-crops` is too generous with EcoCrop's wide ranges:
arabica coffee scores 0.92 at Los Chiles and 1.00 at Parrita (hot lowlands); banana and cacao
score 1.00 at Liberia with 5 dry months; cacao scores 0.93 at Cartago (~1,400 m).

## Proposals (agro-logic review) and what the fact-check found
| Proposal | Fact-check (one search pass; ICAFE, Wood & Lass and Robinson & Galán Saúco PDFs not opened) |
|---|---|
| Coffee: own mean-temperature range, opt 18–23 °C (ICAFE 2011: 17–23 °C, 800–1600 m) | **Not found.** ICAFE figures unconfirmed; DaMatta & Ramalho 2006 exists (doi:10.1590/S1677-04202006000100006) but the numbers were not seen. Get the ICAFE guide before using them |
| Coffee: needs a short dry spell to flower evenly | **Confirmed, ~3 months:** IICA, Hacienda Aquiares (Costa Rica), https://repositorio.iica.int/bitstream/handle/11324/3015/BVE17068933e.pdf |
| Cacao: mean ≥ 21 °C, coldest month ≥ 15 °C | **Partly:** 21 °C mean as a limit in Infoagro (secondary); 15 °C not found in a primary source |
| Cacao: at most ~3 months under 100 mm | **Not found;** sources ask more: 1800–2500 mm/yr well spread (150–200 mm/month), < ~124 mm/month falls short (Redalyc 180376041013; UF/IFAS HS1505) |
| Banana: ~100 mm every month | **Partly:** best yields with ~1900 mm/yr well spread (~160 mm/month); 100 mm/month as a minimum (IPI Bulletin 18 / Embrapa; FAO World Banana Forum) |
| Pineapple: tolerates long dry seasons (CAM) | **Partly:** efficient with water, but water stress cuts fruit size (Carr 2012); minimum ~50–100 mm/month (secondary) |
| Label banana as "banana / plantain" for smallholders | **Partly:** CATIE 2015: plantain and plantain–banana–cacao systems in Bribri/Cabécar territories |
| Los Chiles / Huetar Norte is a main pineapple region | **Confirmed:** Huetar Norte 49 % of the area (CANAPEP via La Nación 2019); Los Chiles is part of it |

## Suggested order
1. Dry months as a scored variable, with per-crop monthly-rain needs from the sources above
   (cacao and banana from ~100–124 mm/month, pineapple 50–100 mm, coffee wants ~3 dry months).
2. Cacao mean temperature from 21 °C (secondary source, say so in `sources`).
3. Coffee temperature only after reading the ICAFE guide.
4. Rerun `agro-logic` on `HEAT_MARGIN_C` and the frost range (set while the app read extremes).

## Potato and onion (annual, catalog only)
EcoCrop's potato optimum (15–25 °C, absolute max 30 °C) scores potato 0.98 at Los Chiles and 0.83
at Cartago, so both stay out of `mvp.yaml` crops. Needed before adding them: a cited tropical
range (cool highlands; e.g. CIP or INTA/MAG Costa Rica guides), onion's dry-season and rain
limits, and crop-specific plan-risk constants (tuber rot and bulb rot with harvest rain).
