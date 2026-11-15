# Follow-up PR: farmer texts, translations and fact-check corrections

> **For the next PR (owner: marceconejo).** Collected 2026-11-15 from the `farmer-language` and
> `fact-checker` reviews of `feat/real-soil-scoring`. Nothing here is fixed yet. Rerun both agents
> after the changes (`.claude/agents/`).

## 1. Decision: every farmer-facing text is bilingual
Return each text as an object instead of a plain string, so the frontend shows Spanish without
translating on its own (month names, decimal commas and crop names are already right):

```json
{"en": "Sowing maize in March is risky: …", "es": "Sembrar maíz en marzo es riesgoso: …"}
```

Applies to: `explanation`, `benefits`, `risks`, `data_gaps`, `evidence`, `fixed_limits`,
`dry_month_note`, rotation rule reasons. It's a contract change (string → object): agree it with
the frontend (David) and do it in one go with section 2. Spanish conventions: decimal comma
(0,91), Spanish months (set, oct, nov), "frijol", "maíz", "primera", "postrera", "encharcamiento",
crop names in Spanish.

## 2. Texts that mislead (fix first)
| # | Text / where | Problem | Suggested EN | Suggested ES |
|---|---|---|---|---|
| 1 | "Strong water fit across the year (1.00)" (`ranking.py` ~83) next to a waterlogging warning | Contradiction: the water category ignores the waterlogging factor; "across the year" covers only two seasons; "1.00" means nothing to a farmer | Drop the benefit when there's a waterlogging warning (or include the factor in the water category). "Rainfall suits these crops in both seasons" | "La lluvia les sirve a estos cultivos en las dos épocas" |
| 2 | Explanation "…: balanced fit across climate, water, soil (score 0.91)" (`ranking.py` ~147) | Same sentence for monoculture and good rotations; ignores the rotation reasons | Mention the top benefit/risk: "Maize then bean: changing family and the bean's nitrogen help; watch for waterlogging. Score 0.91 of 1." | "Maíz y luego frijol: cambiar de familia y el nitrógeno del frijol ayudan; ojo con el encharcamiento. Puntaje 0,91 de 1." |
| 3 | Waterlogging note (`suitability.py`, `crop_season_fit`) | "94% saturated" reads like a field measurement (it's a ~9 km model mean); four ideas in one sentence; **"clay loam drains slowly" is wrong** (moderate): only mention pure clay | "{crop} in {season}: risk of waterlogged soil. Satellite data for the area (~9 km) shows the soil near saturation (94% on average), and {crop} doesn't tolerate standing water. Check how your field drains; raised beds help." | "{cultivo} en {época}: riesgo de encharcamiento. Los datos satelitales de la zona (~9 km) muestran el suelo casi saturado (94 % en promedio) y el {cultivo} no aguanta el agua empozada. Revise cómo drena su terreno; sembrar en lomillos o camas levantadas ayuda." |
| 4 | Dry-soil note (`_stress_note`) | "near the wilting point" is a field claim SMAP can't support; "m³/m³" jargon; no scale | "{crop} in {season}: satellite data for the area (~9 km) shows very dry soil around the roots; the crop may lack water without irrigation" ("fairly dry" when score > 0) | "{cultivo} en {época}: los datos satelitales de la zona (~9 km) muestran el suelo muy seco donde están las raíces; el cultivo podría sufrir falta de agua si no se riega" |
| 5 | pH outside absolute range (`services._fixed_limit_notes`) | Absolute verdict from a 250 m map; lime can correct low pH | "Soil pH {x} (soil map, 250 m) is outside what {crop} tolerates ({a}-{b}). Confirm with a soil test; if right, {crop} won't do well here in any month without liming" | "El pH del suelo {x} (mapa de suelos, 250 m) está fuera de lo que tolera el {cultivo} ({a}-{b}). Confírmelo con un análisis de suelo; si es correcto, el {cultivo} no se daría bien en ningún mes sin encalar" |
| 6 | pH outside ideal (same function) | Map caveat; "lowers the score" talks about the tool, not the farm | "Soil pH {x} (soil map) is a bit outside the best range for {crop} ({a}-{b}); expect somewhat lower yields. A soil test can confirm it" | "El pH del suelo {x} (mapa de suelos) está un poco fuera del rango ideal para el {cultivo} ({a}-{b}); puede rendir algo menos. Un análisis de suelo lo confirma" |
| 7 | Legume reasons (`rotation_rules.py` ~97-104) | The two versions disagree, and **"most of its nitrogen from the air" is wrong for beans (~39 %; fact-check)**; "next crop may need less fertilizer" overclaims | "{crop} (bean family) after {prev}: it takes part of its nitrogen from the air, so it draws less from the soil; its crop residues add a little for the next crop" | "{cultivo} (familia del frijol) después de {anterior}: toma parte de su nitrógeno del aire y gasta menos del suelo; los rastrojos dejan un poco para el siguiente cultivo" |

## 3. Unclear texts
| # | Where | Change |
|---|---|---|
| 8 | Generic risk notes (`suitability._risk_note`) | Label map instead of variable ids (`soil_ph` → "soil pH", rainfall → "rain over the crop cycle"); no "mm/cycle", "absolute limit", "marginal". ES: "demasiada lluvia durante el ciclo (~1300 mm; aguanta hasta 1200 mm)" |
| 9 | Cycle-length note | "Maize needs about 120 days but postrera lasts about 91: harvest falls in the dry months, or use a shorter variety". ES: "El maíz necesita unos 120 días y la postrera dura unos 91: la cosecha caería en verano, o use una variedad más precoz" |
| 10 | Evidence soil line (`services._evidence`) | Show the season saturation behind the waterlogging warning, scales and sources: "Soil: pH 6.4 (soil map, 250 m); near saturation in primera (88 %) and postrera (94 %) (NASA SMAP, ~9 km)" |
| 11 | Evidence climate line | "average 22.7 °C, hottest hours ~29.9 °C, coolest nights ~16.1 °C, ~248 mm of rain per month (NASA POWER, long-term averages)"; Spanish month names |
| 12 | Data gaps (`MEASURED_SOIL_GAPS`) | Drop "L4", "monthly means", "relative saturation". ES: "La humedad del suelo viene de NASA SMAP (satélite + modelo), promedio de un área de ~9 km y de los años 2020-2024; no se midió en su finca" / "El aviso de encharcamiento usa qué tan saturado está el suelo en un área de ~9 km; no ve el drenaje propio de su terreno (pendiente, zanjas)" |
| 13 | Rotation reasons with Latin families (Poaceae, Fabaceae) | Common names: "grass family" / "bean family" (gramíneas / leguminosas) |
| 14 | Mycorrhizae reason | ES: "{anterior} antes de {cultivo}: {anterior} no alimenta los hongos buenos del suelo (micorrizas), y el {cultivo} los necesita para aprovechar el fósforo" |
| 15 | "heavy feeder" | "needs a lot of nitrogen" / "pide mucho nitrógeno" |

## 4. Style and consistency
- One term per idea: "waterlogging"/"encharcamiento" for the risk, "near saturation"/"casi saturado"
  for the data.
- One structure: "<Crop> after <prev>: …" for transitions, "<Crop> in <season>: …" for the rest.
- "Local review: …" items sit in `risks` and double the risk count: consider their own field.
- Frost: "safe at 5 °C or above" (was "safe from 5 °C").

## 5. Fact-check corrections that change data (need the engine owner's OK)
| Item | Now | Correction | Source |
|---|---|---|---|
| Maize `forage_value` | 1 (high) | **0.67**: stover is "highly fibrous… limited digestibility", CP 4-9 % | Feedipedia, maize stover (feedipedia.org/node/16072) |
| Rice `mycorrhizal_affinity` | 0.33, "team estimate" | Keep 0.33 but say **flooded rice** (consistent with the EcoCrop flooded rain ranges); upland rice is colonized | Vallino et al. 2014, Plant Cell Environ., doi:10.1111/pce.12177; FungalRoot, Soudzilovskaia et al. 2020, doi:10.1111/nph.16569 |
| Beans N fixation (text) | "most of its nitrogen from the air" | ~39 % from the air (%Ndfa) | Reinprecht et al. 2020, Front. Plant Sci., doi:10.3389/fpls.2020.01172 |
| FAO-56 p (planned) | rice 0.20 | Rice's p is a fraction of **saturation**, not of available water; cowpea uses the "Green Gram and Cowpeas" row | FAO-56 Table 22, footnote 4 |
| "Beans more sensitive to waterlogging than maize" | rationale in decisions.md | **No source found**; maize: −13 to −26 % depending on stage, 6 days critical | Crop Journal 2022; NSW DPI "Managing waterlogging in crops" |
| Planting calendars (`mvp.yaml` seasons) | primera May–Aug, postrera Sep–Nov | Only older FAO/GIEWS reports confirm roughly Apr–May first season; **find a current MAG/INTA-CR calendar** | FAO/GIEWS Costa Rica reports (2000) |
| Nutrition and N demand traits | team estimates | Not checked: use USDA FoodData Central / INCIENSA tables and nutrient-removal tables | — |

Already fixed in `feat/real-soil-scoring` (stale docs): SMAP penalty −30 % → −15 % in `smap.md`;
`ecocrop.md` no longer says scoring uses mock soil; SMAP NSIDC citation (doi:10.5067/T5RUATAQREF8)
added; the "apante beans avoid waterlogging" rationale replaced with what sources say (rain at
harvest and disease).

## 6. For the `agro-logic` agent
- Is primera/postrera the right calendar for San Carlos? Zona Norte beans are mostly sown late
  (Upala/Los Chiles ~Dec–Feb), and every rotation there gets a waterlogging warning in postrera.
- Residual soil moisture for late sowings (dry-month check counts rain only).
- A primera disease / excess-rain-at-harvest rule for beans (web blight).
- Rotations score postrera as 3 months although maize needs 4 (the dry December is never seen).
