# Technical decisions log

One entry per decision, newest first. Keep each to a few lines: **what**, **why**, and
what would make us revisit it. Changes to `config/mvp.yaml` go here too.

Template:

```
## YYYY-MM-DD — Short title
- **Decision:** …
- **Why:** …
- **Alternatives considered:** …
- **Revisit if:** …
```

---

## 2026-11-15 — NOAA ENSO files: reuse a copy under one day old in live mode
- **Decision:** `NoaaEnso.index()` first asks `JsonCache.peek_fresh(…, MAX_AGE=1 day)` and only
  calls `get_or_fetch` (a download) when the copy is older. The cache key stays `{"index": …}`
  with no date. `cached` mode is unchanged: it serves the saved copy whatever its age.
- **Why:** before this, every live `POST /plan-risk` downloaded both RONI and ONI (two
  synchronous requests, up to 30 s each on a slow CPC) for files NOAA rewrites once a month.
- **Alternatives considered:** a year-month in the cache key (would make the committed snapshot
  miss every new month); `peek` like SRTM (never refreshes); keeping `Last-Modified` /
  conditional requests (more code for the same effect).
- **Revisit if:** a demo needs the newest NOAA value within the hour (lower `MAX_AGE`), or the
  snapshot's `fetched_at` has to be honoured differently.


## 2026-11-15 — Plan-risk farmer texts after the `farmer-language` review (phase 7)
- **Decision (engine owner):** apply the review's must-fix and should-fix items; leave the
  nice-to-have ones (Costa Rican usage: "veranillos", "calurosas", "zanjas", when to do la dobla,
  "En vez de…", "máximas", MERRA-2 gloss) for later. Changes to what a farmer reads:
  - **"habría fallado en N de M años"** (missing "en"), and a new `data_gaps` line defining a
    "failed" year as weather known to badly damage the crop (e.g. 20+ days without rain at
    flowering), not a harvest measurement. The review's "probablemente se habría perdido" was
    **not** adopted: it claims a crop loss we don't measure.
  - **Dry-start action** no longer says "wait for the rains": on a late sowing the rains are
    ending and the card's own alternative says to sow earlier. Now "Siembre solo con el suelo
    húmedo… Si las lluvias ya se están yendo, siembre antes en vez de esperar".
  - **"(vea las opciones abajo)" dropped**: alternatives only exist when something failed less.
  - **Insurance:** "Pregunte al INS **si** el Seguro Agrícola cubre este riesgo en su cultivo"
    (the old "para este riesgo" implied coverage).
  - **El Niño split note:** conditional and with a subject ("Esta siembra habría fallado en…"),
    "y" before the last item, "años normales" instead of "neutrales", and a small-sample warning
    ("Son pocos años y puede ser casualidad"). The few-years branch fixes the agreement
    ("Solo hubo 1 año de El Niño…: no alcanza para comparar").
  - **EcoCrop limits attributed, not stated as facts:** "menos de los 300 mm que se suelen
    indicar para el frijol (FAO)" and "El cultivo habría dependido de la humedad que quedaba en el
    suelo" (a guess, said as one); the too-wet summary says "muy por encima del límite de 700 mm
    que da la FAO" with the typical rain rounded to 100 mm. Sorghum's 700 mm kept as is (not an MVP
    crop; the engine owner declined a fact-check).
  - **Second rain source:** "tome las cifras de lluvia como aproximadas" instead of "algunos
    años saldrían distintos", which was never computed.
  - **Soil wetness** says its scale and origin: "se secó hasta 55 % (100 % = empapado;
    estimación de modelo)", "el suelo casi empapado (89 %)".
  - **Explanations** start with "El peor año, 2002: …" so the farmer knows it's the worst year.
  - **Per-crop notes start with the crop name and sowing date** ("Frijol, siembra del 15 de
    noviembre: …"), as the frontend guide requires; the warm-nights note is reworded in plain
    words ("hacen que la planta pegue menos vainas", "no se cuenta como año malo") and the
    too-few-seasons note follows the same prefix rule.
  - **NOAA jargon:** "ASO 2026" → "ago–oct 2026"; the ONI comparison is one line for all sowing
    months ("algunos años cambiarían de grupo (El Niño, La Niña o normal): 3 de 25 en noviembre,
    5 de 26 en setiembre") instead of one near-identical line per month.
  - Rain data gap: "es un promedio de un cuadro de unos 10 km de lado, no se midió en su finca".
- **Revisit if:** the nice-to-have items are applied (same review, items 16–30).

## 2026-11-15 — El Niño in plan-risk: NOAA CPC RONI, not the legacy ONI (phase 6)
- **Decision (engine owner, after research):** label each sowing year, `enso_split` and
  `enso_now` with NOAA CPC's **Relative Oceanic Niño Index (RONI)**, and report in `data_gaps` how
  many sowing years the legacy **ONI** would label differently. The plan named `oni.ascii.txt`.
- **Why RONI:** NOAA CPC switched official ENSO monitoring, prediction and classification to RONI
  on 2026-02-01 (NWS Public Information Statement 26-05, 2026-01-13). Per NOAA it is "less
  sensitive to the chosen base climatology period" (comparable across our 2000–2025 record, which
  spans several ONI base periods) and "better aligned with the intensity of rainfall anomalies".
  ONI's file is still updated "for continuity". No study found comparing the two for Central
  American rainfall (the one Costa Rican study found, Quesada 2024, San Ramón, uses ONI).
- **Effect:** labels differ for 3–5 of 25–26 sowing years depending on the month (Sep: 2016, 2017,
  2018, 2024, 2025; Nov/Dec: 2016, 2019, 2024). `enso_now` = ASO 2026 RONI +1.97 (ONI: +2.46),
  El Niño either way. The contract field stays `enso_now.oni`; only its description now
  says RONI.
- **Label rule (placeholder, `ENSO_THRESHOLD_C`):** a sowing year is `el_nino` if the index for
  the 3-month season centred on the sowing month is ≥ +0.5 °C, `la_nina` if ≤ −0.5 °C, else
  `neutral`. Simpler than NOAA's episode rule (5 consecutive overlapping seasons).
- **Split:** failed / evaluated years per phase; if El Niño or La Niña has fewer than 4 years
  (`MIN_YEARS_TO_COMPARE`), the note says there are too few to compare. The note never claims
  significance and always says "a pattern in past years, not a forecast".
- **Source and cache:** `app/integrations/noaa_enso.py`, namespace `noaa_enso`, key
  `{"index": "RONI" | "ONI"}`. **Deviation from the plan:** no year-month in the key. In `live`
  mode `JsonCache` always refetches (falling back to the last good copy), so new months arrive
  anyway; a dated key would make the committed snapshot miss every new month in `cached` mode.
- **NOAA unavailable:** the El Niño block is optional in the contract, so if both the fetch and
  the cache fail, plan-risk still answers: `enso_now`, `enso_split` and `years[].enso` are `null`,
  `data_gaps` says El Niño data isn't available, and a WARNING is logged (errors.md rule 9:
  handled and continued). Every other source still fails the request as before.
- **Real results (IMERG + RONI):** Los Chiles beans Nov 15 failed 2/25, **both in El Niño years**
  (2002, 2018): 2 of 8 El Niño vs 0 of 12 La Niña and 0 of 5 neutral; 2020 (Eta/Iota) is La Niña.
  Alajuela beans Sep 1 failed 1/26 (2015, El Niño). Maize May 15: only 1 El Niño year at that
  date, so the note says too few to compare.
- **Revisit if:** a study compares RONI and ONI for Central American rainfall, or NOAA changes the
  official index again.

## 2026-11-15 — Plan-risk fact-check: text corrections, sorghum 36 °C, night heat calibrated
- **`fact-checker` review** of every source in `plan_advice.py` and `plan_risk.py`. Applied with the
  engine owner's OK:
  - **Insurance:** INS renamed "Seguro de Cosechas" to **"Seguro Agrícola"** in 2018 (El Mundo CR,
    2018-03-13). The action now says "Pregunte al INS por el Seguro Agrícola para este riesgo".
  - **La dobla:** the stalk is bent below the ear so the ear hangs down and sheds rain (Munguía
    Ulloa 1995, Uniciencia, UNA). The old text said to fold the ear.
  - **Timing:** lomillos are built at sowing → "En la próxima siembra, siembre en lomillos…" (UCR
    bean trials, Agronomía Mesoamericana). Web blight starts at flowering → "Desde la floración,
    vigile la mustia hilachosa…; cubrir el suelo con rastrojo reduce el salpique" (Galindo et al.
    1983, Phytopathology 73:610-615).
  - **Varieties:** no heat-tolerant bean is released in Costa Rica (CIAT lines only, Cruz et al.
    2023); Nambí is short-cycle and drought-tolerant → "variedades de ciclo corto o tolerantes al
    calor y la sequía", and "agencia de extensión del MAG".
  - **Sorghum flowering heat limit 38 → 36 °C** (Prasad et al. 2006, Agric. For. Meteorol.
    139:237-251). No demo result moves (sorghum is "too wet" at both points).
  - **Comments:** sources now cited in place; Sivakumar 1988 described correctly (≥ 20 mm in 3 days,
    no dry spell > 7 days in the next 30, Sahel), so our rule is "inspired by" it; rice 35 °C air ≈
    33.7 °C panicle tissue (Jagadish et al. 2007); FAO-56 budget "roughly 1–2 weeks"; maize, bean,
    rice and sorghum stage windows sourced (IITA, CIAT 1986, IRRI, K-State). Still unsourced:
    cowpea's window (uses the beans one), a cowpea day-heat threshold, "keep seed to re-sow"
    (common practice), "a palmo" (common-sense cue), and "maize never fails on harvest rain" (a
    modelling choice).
- **Night heat for beans and cowpea: calibrated, not added.** Hot nights (> 20 °C) are the main
  heat driver for bean and cowpea pod set (Cruz et al. 2023; Hall's group for cowpea), and Porch &
  Jahn 2001 used 32/27 °C day/night. On real MERRA-2 Tmin (23 flowering nights per season):
  - Los Chiles: mean monthly minimum 21.4–23.8 °C all year; nights > 20 °C in a typical year: 23
    of 23 (Sep 1, Oct 15, Nov 15), 21 (Dec 1); every year has ≥ 5. Only a > 23 °C threshold
    varies from year to year, and no source supports it.
  - Alajuela: nights > 20 °C, median 18 (Sep 1), 11 (Oct 15), 4 (Nov 15), 3 (Dec 1).
  - Conclusion: at 20 °C a yearly check would flag every season at Los Chiles, the national bean
    zone. Warm nights there are a property of the place, not a yearly risk. Not added as a yearly
    check.
  - **Decision (engine owner): a per-planting note, no score.** For beans and cowpea
    (`WARM_NIGHT_CROPS`), when a typical season (median) has ≥ 5 (`WARM_NIGHT_NOTE_NIGHTS`)
    flowering nights above 20 °C (`WARM_NIGHT_C`), `data_gaps` gets "Common bean: nights during
    flowering are usually warmer than 20 °C here (23 of 23 nights in a typical season). Warm nights
    can reduce pod set; it isn't counted as a failure because it happens almost every year". Shown
    at Los Chiles (all bean/cowpea dates) and Alajuela Sep 1 (18 of 23); not at Alajuela Nov 15
    (4). The 5-night count is a placeholder (same as the day-heat stress count).
  - **Frontend guide** updated: real texts, the too-wet summary, crop-named notes in `data_gaps`.

## 2026-11-15 — `POST /plan-risk` wired to real data (phase 5)
- **Decision:** `services.plan_risk` validates the point and crops (422 before any fetch), reads
  the daily history 2000-06-01 → 2025-12-31 (`PLAN_RISK_HISTORY_START/END`, fixed: see the rain
  source entry) through a new `DailyHistorySource` protocol (`Sources.history`: NASA POWER in
  live/cached, a deterministic mock in mock mode; `Sources.daily` and `daily_weather` untouched),
  turns it into the domain's `DailyHistory`, runs `stress_test`, then actions, alternatives (MVP
  crops only) and texts from `plan_advice`.
- **Response details:**
  - `summary`: "Would have failed N of M years, mostly because of X" (the cause behind the most
    failed years), or "… watch for X (n of M years)" when nothing failed, or "not enough complete
    seasons" under 10.
  - `causes[].severity` is the worst year for that cause; the contract description now says
    causes that failed a year come first (description-only change, agro-logic review).
  - `years_evaluated` spans all plantings; each planting's own count is its `years` length.
  - `data_gaps`: satellite rain ~10 km, MERRA-2 model ~50 km, years covered, weather only / no
    irrigation, El Niño pending, and how far MERRA-2 rain differs from IMERG at the point (30 %
    less at Los Chiles), plus one per planting with too little history.
  - ENSO fields are `null` until phase 6.
- **Demo data:** fetched live once for Los Chiles and Alajuela into the local runtime cache
  (`.cache/`, gitignored), then **copied to the committed snapshot (engine owner's OK, phase 7)**:
  `app/cache/snapshots/nasa_power_daily_history/` (2 files, 2.1 MB) and `noaa_enso/` (RONI + ONI,
  40 KB). Copied by hand instead of `make cache-snapshot`, which would also have committed an
  unrelated 1.2 MB `nasa_power_daily` file (Los Chiles 1991–2025, no endpoint uses it). Verified
  as a fresh clone (empty runtime cache, `DATA_MODE=cached`): every endpoint 200 at both points.
- **Crops that don't belong here (engine owner's OK, 2026-11-15):** when a typical season (median
  cycle rain over the evaluated years) gets more rain than the crop's EcoCrop `rainfall_mm.abs_max`,
  the summary says "Too wet for {crop} here: a typical season gets about X mm … tolerates at most
  Y mm. Not recommended at this place.", even with 0 failed years, and that crop is never offered
  as an alternative. No new contract field. Only sorghum triggers it at the demo points (Los Chiles
  1,287 mm, Alajuela 1,363 mm vs 700 mm); maize, rice, beans and cowpea don't. Not a yearly
  check, so it doesn't bring back `cycle_rain_high`.
- **Real results, Los Chiles:** beans Nov 15 → 2/25 failed (dry spells at flowering; options: sow
  Nov 1 or Oct 18, 0/25); maize May 15 → 0/25; beans Sep 1 → 0/26 (harvest rain stress 5/26).

## 2026-11-15 — Plan-risk actions and alternatives (phase 4)
- **Decision:** `app/domain/plan_advice.py`.
  - **Actions:** 2–3 bilingual actions per cause (`ACTIONS`), crop-specific ones first
    (`CROP_ACTIONS`: maize "doblar la mazorca" and beans "mustia hilachosa" at a wet harvest), and
    "Ask INS about crop insurance for this risk" appended only to causes that failed a year. It
    only asks: no claim about what INS covers. Each action's source is a comment next to it.
  - **Alternatives:** the same stress test re-run with the sowing date shifted −28, −14, +14, +28
    days (`SOWING_SHIFTS_DAYS`), and with every other MVP crop (`mvp.yaml` `crops`, never the
    whole catalog) on the plan's date. Kept only if the **failure rate** is lower than the plan's
    (rates, not counts: a shifted date can evaluate one season fewer) and the option has enough
    history. Ranked: lowest rate, then **same crop on another date before another crop** (a
    date change is easier for a farmer than a crop change; the plan said "then shift size",
    which put another crop, a 0-day shift, ahead of a 2-week shift), then smaller shift, then
    crop id. At most 3 (`MAX_ALTERNATIVES`).
- **Example, Los Chiles, IMERG:** beans Nov 15 (fails 2/25) → "Sow 2 weeks earlier (November 1):
  would not have failed in any of the 25 years", "Sow 4 weeks earlier (October 18): …". Beans
  Dec 15 (13/25) → Nov 17 (2/25), Dec 1 (5/25).
- **Sources to verify (`fact-checker`, phase 7):** most action sources are marked "from memory,
  unverified" in the code: mulch (FAO Conservation Agriculture), early varieties (CIAT), onset
  rule (Sivakumar 1988), weeds and water (FAO), post-harvest drying (FAO), raised beds, the
  doubling practice, heat-tolerant bean availability in Costa Rica. Verified: flowering is the most
  water-sensitive stage (FAO crop information, maize); web blight with wet harvests in Zona Norte
  (farmer-texts fact-check 2026-11-15). All texts go to the `farmer-language` review in phase 7.
- **Revisit if:** the fact-checker can't source an action (drop or reword it).

## 2026-11-15 — Plan-risk thresholds after the agro-logic review; demo point relabeled Los Chiles
- **Decision (engine owner, after an `agro-logic` review the same day):** the review's blockers
  and should-fix items are applied in `app/domain/plan_risk.py`:
  1. **`cycle_rain_high` dropped** (never produced; kept in the API enum). EcoCrop rainfall ranges
     are annual figures (FAO) applied per cycle here, and excess rain hurts through waterlogging,
     disease and harvest wetness, which have their own checks. It flagged maize in 19/25 years.
  2. **`cycle_rain_low` reworked:** no "below optimum" stress. Below EcoCrop `abs_min` only: a fail
     when the root zone also dries in the second half of the cycle (mean `GWETROOT` < 0.5,
     `CYCLE_LOW_SOIL_WETNESS`), otherwise a stress worded "the crop relied on water stored in the
     soil". Plan-risk assumes no irrigation (to be said in `data_gaps`, phase 5).
  3. **Fail causes first** in `cause_summaries` (then frequency): a rare fail matters more than a
     frequent stress.
  4. **`harvest_wet`:** soil wetness never triggers on its own (only extra evidence with rain, for
     crops needing drainage). Rain thresholds per crop (`HARVEST_RAIN_MM`): beans and cowpea 150 /
     250 mm; maize, rice, sorghum stress from 250 mm and never fail (ears doubled in the field).
  5. **Flowering windows per crop** (`FLOWERING_FRACTIONS`): maize 45–65 %, beans and cowpea
     35–60 %, rice 65–85 % (the old 45–65 % caught panicle initiation, not flowering), sorghum
     50–70 %.
  6. **Flowering heat limit per crop** (`FLOWERING_HEAT_LIMIT_C`) instead of the survival limit:
     maize, rice, cowpea 35 °C, sorghum 38 °C, **beans 32 °C**. The review suggested 30–32 °C for
     beans "after checking real Tmax": at 30 °C, Sep 1 beans showed heat stress in 7/26 years
     (Sep–Dec mean daily max is 28–29 °C, beans are grown there), Nov 15 beans failed 10/25 instead
     of 6/25; 32 °C (= EcoCrop abs_max) keeps only real heat waves.
- **Results, Los Chiles (11.0, −84.6), IMERG 2000-06 → 2025-12, before → after** (failed/evaluated):

  | Plan | Before | After | Main causes after |
  |---|---|---|---|
  | maize May 15 | 1/25 (cycle_rain_high 19) | 0/25 | late_dry_start stress 2 |
  | beans Sep 1 | 0/26 (harvest_wet stress 17) | 0/26 | harvest_wet stress 5 |
  | beans Nov 15 | 12/25 | **6/25** | flowering_dry_spell fail 13, cycle_rain_low stress 11 |
  | rice May 15 | 0/25 (cycle_rain_low stress 22) | 0/25 | late_dry_start stress 2 |
  | sorghum May 15 | 25/25 (cycle_rain_high) | 0/25 | harvest_wet stress 4 |
  | cowpea Sep 1 | 0/26 (harvest_wet 17) | 0/26 | harvest_wet stress 5 |

- **Flowering dry spell judged on the soil during the run (applied after the table above, engine
  owner's OK):** the 6 remaining Nov 15 bean failures were all 15+ day dry runs at flowering
  (mid-Dec to early Jan; IMERG Dec 147 mm, Jan 53 mm on average). Now: stress if the run is ≥ 10
  days and the minimum `GWETROOT` during the run is < 0.7; fail if ≥ 15 days with minimum < 0.6,
  or ≥ 20 days whatever the soil; length alone when there is no wetness data. Replaces the old
  "≥ 15 days, or ≥ 10 with mean flowering wetness < 0.5" rule. Result: **beans Nov 15 → 2/25**
  (both long flowering dry spells; worst 2002, 23 dry days), Dec 1 → 5/25, Dec 15 → 13/25 (sowing too deep into the
  dry season); every other plan in the table unchanged.
- **Still open (review's "nice to have", not applied):** soil gate on the establishment dry run, "re-sow" wording, a 2020 "sources disagree" flag, an in-cycle heavy-rain
  waterlogging check, and showing sorghum as "too wet for sorghum here" (suitability) instead of a
  clean 0/25.
- **Unverified values** for the `fact-checker` (phase 7): rice and bean stage timing, the maize,
  rice, sorghum and cowpea heat limits, the Sivakumar onset rule, the maize-doubling practice.
- **Demo point relabeled "Los Chiles (Zona Norte)":** (11.0, −84.6) is ~12 km from Los Chiles town
  and ~75 km from Ciudad Quesada, the "San Carlos" most people picture. It sits in the national
  bean zone (Upala, Los Chiles, Guatuso). Coordinates and cached data unchanged. Renamed in backend
  docs, Bruno requests, code comments and test labels; earlier entries in this log keep "San
  Carlos" as written. **Team files still saying San Carlos** (owners to decide): `README.md`,
  `PROJECT_CONTEXT.md`, `docs/pilot-baseline/`, `docs/frontend-requirements-proposal.md`,
  `docs/farmer-input-proposal.md`, `tools/local-mvp-preview/`, `odd/tasks/local-mvp-preview.md`,
  `.claude/agents/fact-checker.md`. Which canton the point falls in is unverified.
- **Revisit if:** the fact-checker or a Zona Norte extension agent disagrees with a value.

## 2026-11-15 — Plan-risk stress-test engine and its placeholder thresholds (phase 3)
- **Decision:** `app/domain/plan_risk.py` replays "sow crop X every year on day D" over the daily
  history. Season year = sowing year; harvest = sowing + `cycle_days` (crossing the new year is
  fine; Feb 29 → Feb 28 in non-leap years). A season counts only if all its days are in the history
  and < 10 % of its rain days are missing (window totals are rescaled from the days present; a
  missing day breaks a dry run). Fewer than 10 valid seasons → `not_enough_history` flag (the
  service answers 200 + data gap). Outcome per year: `fail` if any check fails, else `stress` if
  any is stressed, else `ok`. `failure_rate` = failed / evaluated.
- **Stages (fractions of the cycle):** establishment days 0–19, flowering 45–65 %, harvest = last
  15 days. **Checks** (dry day < 1 mm, ETCCDI):
  - `late_dry_start`: establishment rain < 30 mm or a dry run ≥ 7 days → stress; < 10 mm → fail.
  - `flowering_dry_spell`: longest dry run ≥ 10 days → stress; ≥ 15 days, or ≥ 10 with mean
    `GWETROOT` < 0.5 → fail.
  - `cycle_rain_low` / `cycle_rain_high`: cycle rain outside the crop's EcoCrop `rainfall_mm` opt
    range → stress; outside abs → fail.
  - `harvest_wet`: harvest-window rain ≥ 150 mm, or mean `GWETROOT` ≥ 0.85 for crops that need good
    drainage → stress; rain ≥ 250 mm → fail.
  - `flowering_heat`: days in flowering with max > the crop's `temperature_c.abs_max` (the limit
    `suitability.heat_range` uses): ≥ 5 → stress, ≥ 10 → fail. `HEAT_MARGIN_C` doesn't apply: it
    ramps a season mean, not a count of days.
  All are **placeholders** pending the `agro-logic` review (phase 7); listed in `backend/AGENTS.md`.
- **Sanity check, San Carlos (11.0, −84.6), IMERG 2000-06 → 2025-12** (failed / evaluated):
  - maize May 15: **1/25** failed; `cycle_rain_high` in 19 years (IMERG gives ~1,300 mm over
    May–Sep vs the EcoCrop optimum 600–1,200 mm), `harvest_wet` stress 11, `late_dry_start` 2.
  - beans Sep 1: **0/26** failed, `harvest_wet` stress 17 (2020: 201 mm + soil 99 % wet; 2024: soil
    100 % wet). The probe's "harvest rain/waterlogging in 2020 and 2024" **is reproduced, as stress**.
  - beans Nov 15: **12/25** (cycle rain too low in 23, flowering dry spell in 9): sowing into the
    dry season fails often, as expected.
  - sorghum May 15: **25/25** (EcoCrop sorghum `abs_max` is 700 mm per cycle; San Carlos gets
    ~1,300). Consistent with the suitability score; sorghum isn't grown in this wet zone.
- **Gap vs the MERRA-2 probe, explained (not tuned):** the probe found late starts in 12 of 35
  years from the rain *onset date*; this engine counts too little rain in the 20 days after a fixed
  sowing date, and IMERG has more rain than MERRA-2 (24 of 26 years), so `late_dry_start` shows
  in only 2 of 25 maize years. Run on MERRA-2 rain the same engine gives maize 4/25 and rice 21/25
  failed (MERRA-2's lower totals push rice below its 1,000 mm minimum), which is why we don't mix sources.
- **For the agro-logic review:** (1) `cycle_rain_high` flags maize in most years at San Carlos
  although maize is grown there: EcoCrop's global `opt_max` may be too low for Zona Norte, or excess
  rain should be judged by waterlogging/harvest rather than by cycle total. (2) `GWETROOT` ≥ 0.85
  at harvest triggers often in this wet zone; compare with SMAP levels. (3) the stage fractions.
- **Revisit if:** the review changes a threshold (new entry with before/after numbers).

## 2026-11-15 — Plan-risk rain source: GPM IMERG via NASA POWER (phase 2)
- **Decision:** the plan-risk stress test uses **IMERG** daily rain (`IMERG_PRECTOT`, ~0.1°) from
  the NASA POWER daily API, with MERRA-2 `T2M_MAX`/`T2M_MIN` and `GWETROOT` (~0.5°). New adapter
  method `NasaPowerClimate.daily_history`, own cache namespace `nasa_power_daily_history`, so
  `daily_weather` and its cache keys are untouched. Only seasons IMERG fully covers are evaluated
  (IMERG starts 2000-06-01, ~2-month latency). Sources are never mixed across years. MERRA-2
  `PRECTOTCORR` is fetched in the same request only to report the gap in `data_gaps`.
- **Why:** at San Carlos IMERG is higher than MERRA-2 in 24 of 26 years (14–126 %), consistent with
  MERRA-2 underestimating tropical convective rain and spreading it into fewer dry days, which
  would undercount dry spells. IMERG's ~10 km cell is also closer to a farm than MERRA-2's ~55 km.
- **Verified live (2026-11-15):** IMERG needs `time-standard=UTC` (with LST it is all −999), so days
  are UTC days; units `mm/day`, `GWETROOT` `1` (fraction); details in `docs/sources/nasa_power.md`.
- **Caveat found:** the two sources disagree sharply on hurricane Eta: 2020-11-03 has 513 mm in
  MERRA-2 and 4 mm in IMERG; November 2020 is 1,010 vs 328 mm. 2024 shows a similar MERRA-2 spike.
  So the "beans harvest rain in 2020" result from the MERRA-2 probe may **not** reproduce with
  IMERG. Phase 3 reports what IMERG shows and explains the gap; it does not tune to match. Which
  source is closer to gauges is unverified (IMN station data would settle it).
- **Fixed history range (engine owner, 2026-11-15):** the service requests **2000-06-01 →
  2025-12-31**, a constant, not "up to last month". A moving end date would change the cache key
  every month and the committed demo snapshot would stop matching (`cache_miss` in `cached` mode).
  Cost: 2026 seasons aren't evaluated. Move the end date forward deliberately, together with a new
  snapshot.
- **Revisit if:** gauge data shows IMERG misses Eta/Iota-type events in Zona Norte (then consider
  flagging years where the two sources disagree strongly instead of trusting either).

## 2026-11-15 — `POST /plan-risk` contract: "when could this plan fail?" (phase 1)
- **Decision (engine owner):** new endpoint `POST /plan-risk` (plan: `docs/follow-ups/plan-risk.md`).
  The farmer sends a point and 1–4 plantings (crop + sowing month/day); each planting is replayed
  against past years of daily weather and evaluated alone (no rotations). The response gives, per
  planting, failed years and rate, causes with the years they hit, actions, per-year outcomes, an
  El Niño split and up to 3 better alternatives, plus the current ENSO phase. Phase 1 ships the
  contract, schemas and a fixed example response so the frontend can start.
- **Answers to the open questions:**
  - Every message (summary, explanations, actions, labels, notes, data gaps) is `LocalizedText`,
    English and Spanish. Error messages stay English, as everywhere.
  - Plantings: 1–4 per request, explicit date only. No season names (`primera`/`postrera`) yet;
    they can be added later as an optional field. `sowing_day` defaults to 1 and is validated
    against the month (Feb 29 allowed; non-leap years will use Feb 28).
  - Fewer than 10 valid seasons: **200 with a `data_gaps` entry**, no new error code.
  - Alternatives use only the `mvp.yaml` crops, never the rest of the catalog.
  - ENSO is in the MVP. Cut order if time runs short: stretch → ENSO split → alternatives.
    `enso_now` and `enso_split` are nullable so the response still works without NOAA data.
  - `EnsoGroup.years` is a count of evaluated years in that phase (not a list); the per-year
    phase is in `years[].enso`.
- **Revisit if:** the frontend needs season names, or the stress-test thresholds (phase 3, logged
  separately) change what a "failed" year means.

## 2026-11-15 — Production at terracosmos.space (Railway Trial + Cloudflare DNS)
- **Decision:** production is live at https://terracosmos.space. The domain is registered at
  Cloudflare. The apex CNAME points to Railway as DNS only, so Railway issues the certificate. The
  Railway service sets `PORT=8000` to match the domains' target port. `www` is a proxied placeholder
  with a 301 redirect rule to the apex, because Railway Trial allows one custom domain. Current
  setup and pending items: `docs/deploy.md`.
- **Why:** the Cloudflare domain was ready, and the GoDaddy offer isn't needed. Keeping Cloudflare
  as DNS only (no proxy) avoids double TLS and certificate issues.
- **Alternatives considered:** a Cloudflare-proxied apex (needs SSL mode Full and adds a layer to
  debug); `www` as a second Railway domain (needs Hobby).
- **Revisit if:** the team upgrades to Railway Hobby (move `www` to Railway), or the Trial ends
  before judging does.

## 2026-11-15 — Deploy: one Railway service (API + static frontend), deployed from GitHub Actions
- **Decision:** the root `Dockerfile` builds one image that runs the API and serves `frontend/` at
  `/app` (`FRONTEND_DIR`; `/` redirects there). Railway runs it in `cached` mode, so production
  needs no secrets and never calls external APIs. `.github/workflows/deploy.yml` deploys after CI
  passes on `main`, or manually from **Actions → Deploy**, with a Railway project token stored as a
  repo secret. `frontend/` is a framework-free skeleton (demo point → `POST /recommendations`) that
  #14 can replace; the image just copies the folder, so a build step can be added later.
- **Why:** all six team members can deploy without a Railway account or seat (Vercel Hobby blocks
  deploys from other authors on a private repo). Same origin means no CORS setup. One service is
  one URL to keep alive for judging. Steps: `docs/deploy.md`.
- **Alternatives considered:** Vercel for the frontend plus Railway for the API (two platforms and
  CORS); GoDaddy hosting (shared PHP hosting can't run FastAPI; its free domain can still point to
  Railway); Google Cloud Run (free credits but more setup; the same image runs there).
- **Revisit if:** the frontend needs a Node build or server rendering, or Railway costs become a
  problem after the hackathon.


## 2026-11-15 — Farmer-facing texts in English and Spanish, reworded after review
- **Decision (engine owner):** every text a farmer or judge reads is returned as
  `{"en": ..., "es": ...}` (`LocalizedText`): `explanation`, `benefits`, `risks`, `data_gaps`,
  `evidence`, `notes`, `fixed_limits`, `dry_month_note`. The domain builds them as `Text(en, es)`
  (`app/domain/text.py`), both languages side by side so they can't drift. Spanish uses Costa Rican
  terms (frijol, maíz, primera, postrera, encharcamiento, "setiembre"), a decimal comma and Spanish
  month names. Crops gain `name_es` (CSV and `Crop` schema). Error messages stay English.
- **Breaking for clients:** those fields change from string to object. There is no frontend yet,
  so nothing breaks today.
- **Rewording (`farmer-language` review):** no more "Strong water fit (1.00)" next to a
  waterlogging warning; the explanation names what helps and what to watch instead of "balanced
  fit" for every rotation; waterlogging and dry-soil notes say the data is satellite + model over
  ~9 km (no field-level claims, no m³/m³); "can drain slowly" only for clay, silty clay and sandy clay
  (not clay loam); pH notes cite the 250 m map and suggest a soil test (and liming); plain labels
  instead of variable ids, Latin family names and "heavy feeder"; crop names lower-case mid-sentence.
- **Data corrections (`fact-checker`, with sources):** maize `forage_value` 1 → 0.67 (Feedipedia:
  stover is fibrous, low digestibility); rice `mycorrhizal_affinity` 0.33 now cites Vallino et al.
  2014 (flooded rice); the legume reason says beans take *part* of their nitrogen from the air
  (~39 %, Reinprecht et al. 2020), not most.
- **`agro-logic` review follow-ups (2026-11-15):** the clay note now says "can drain slowly" (texture
  is a hint, not a measurement: clayey Oxisols/Ultisols in Zona Norte are often well aggregated and
  drain fine, and the 250 m texture can disagree with the ~9 km SMAP wetness); texture never changes
  the score. The benefit list now depends on the waterlogging warning: when water scores strong but
  a waterlogging warning exists, "rain and soil moisture suit" is replaced by "enough rain, but watch
  drainage" (ranking score unchanged). Maize `market_note` now says its stover is fibrous and
  low-protein, matching `forage_value` 0.67.
- **Spanish gender (2026-11-15):** the CSV gains `gender_es` (`m`/`f`, required, validated), and
  sentences use `CropProfile.the_es` / `of_the_es` ("el maíz", "la yuca", "del maíz", "de la yuca")
  instead of a hardcoded "el". All current crops are masculine, so no output changed. Adding a
  feminine crop now only needs `f` in its row. No runtime machine translation: it needs the network
  (the demo is offline), mis-words Costa Rican terms ("setiembre", "frijol") and is not deterministic.
- **Sorghum `forage_value` 1 → 0.67 (`fact-checker`, 2026-11-15):** no source rates sorghum above
  maize stover. Feedipedia sorghum straw (node 12618): crude protein 3.7 %, organic-matter
  digestibility 53 %, vs maize stover ~3.9 % and ~49 %. Whole-plant forage or silage sorghum is a
  different use; the field values the crop *or its residue*, as for maize. Cowpea (1, team
  estimate) and rice (0.33, team estimate) are still uncited.
- **Revisit if:** the frontend prefers message codes plus parameters.

## 2026-11-15 — Planting windows: dry-month check (no more dry-season maize sowing)
- **Problem:** the cycle's rain total hid dry months. Maize sown in March in Alajuela gets 29 and
  76 mm in its first two months, but May and June bring the total to 534 mm, so March counted as a
  good sowing month (the seed would sit in dry soil). October passed with a dry December–January.
- **Decision (engine owner, after an `agro-logic` review):** every month in the field except the
  last (harvest; dry weather is wanted there) is checked. The driest one is scored on a ramp from
  `rain_abs_min / (n + 1)` (0) to `rain_opt_min / (n + 1)` (1), n = months in the field (Recocrop
  splits EcoCrop ranges per month the same way). It must score >= 0.5 (`MARGINAL_SCORE`): maize and
  beans pass at ~100 mm, close to Oldeman's (1975) wet-month bar for upland crops (from memory).
  It only decides good sowing months (not averaged into crop or rotation scores). Farmer note in
  `SowingMonth.dry_month_note`, e.g. "Sowing Maize in March is risky: March usually gets only 29 mm
  of rain, and Maize needs about 100 mm a month to establish and grow (at least 80)".
- **Effect:** maize May–Sep at both demo points (was Apr–Oct in San Carlos, Mar–Oct in Alajuela);
  Alajuela beans and cowpea lose April (76 mm); San Carlos sorghum keeps no window.
- **Known limits (documented, not fixed):** stored soil water isn't counted, so residual-moisture
  sowings (Zona Norte beans in Nov–Dec) still fail; bean windows stay wide because primera disease
  (web blight) needs a separate rule; rotations score postrera (Sep–Nov) as 3 months although maize
  needs 4, so the dry December is never seen there.
- **Revisit if:** soil-water carry-over is added (e.g. pass a month after a month >= 2 × optimum).

## 2026-11-15 — Soil moisture scores dry soil only; waterlogging check for well-drained crops
- **Decision (engine owner, after an `agro-logic` review):**
  - `GENERIC_SOIL_MOISTURE` is dry-side only: 0 at or below 0.10 m³/m³, 1 from 0.20, no upper
    limit (was ideal 0.20–0.40, max 0.55). SMAP's absolute m³/m³ depend on its model's soil, and
    excess water is already covered by each crop's rainfall upper limits. Dry soil gets a plain note
    ("root-zone soil is dry… expect water stress without irrigation").
  - **Waterlogging:** SMAP `sm_rootzone_wetness` (relative saturation 0–1, same model, comparable
    across soils) is fetched with the moisture. For crops that need good drainage, the cycle's mean
    wetness lowers the score from 0.80 (no effect) to −30 % at 0.95, with a warning from 0.85
    ("waterlogging risk… check drainage or use raised beds"). Never a veto.
  - **`needs_good_drainage`** is imported from EcoCrop (`drar`): rice tolerates poorly drained soil
    (`false`); beans, maize, sorghum, cowpea need good drainage (`true`).
- **Rejected:** per-crop moisture ranges (no source gives them in m³/m³); dividing SMAP moisture by
  OpenLandMap field capacity (different soil models and depths: contradictory results).
- **Waterlogging size (second `agro-logic` review, adopted by the engine owner):** at most −15 %
  (`WATERLOGGING_MIN_FACTOR` 0.85, was 0.70). A real waterlogging event costs more, but only in
  poorly drained fields, which ~9 km monthly data can't tell apart; −30 % treated a regional model
  value as the field. Thresholds 0.80 / 0.95 / 0.85 kept as placeholders.
- **Planting windows only warn about waterlogging:** a month's "good" decision ignores the factor
  (the data can't see drainage, slope, raised beds or ditches). Each sowing month gets
  `waterlogging_risk`; crop and rotation scores still include the penalty.
- **Effect (real data):** San Carlos warns in postrera (85 % saturated) for maize, beans and cowpea,
  ~5 % penalty (mean wetness 0.85). Zona Norte beans are mostly sown late (Upala/Los Chiles cycle
  ~Dec–Feb); sources found cite rain at harvest and disease, not waterlogging, as the reason
  (fact-check 2026-11-15). Alajuela keeps rainy-season windows
  (beans Apr–Oct, maize Mar–Oct) with warnings; with −30 % they had shrunk to Mar–May.
- **Open:** Alajuela maize still opens in March (dry season): the rain or dry-soil checks may be too
  loose for the sowing month; separate review.
- **Later (review):** FAO-56 water-stress coefficient per crop (depletion fraction p) for the dry
  side; SMAP `land_fraction_saturated`; clay texture raising the waterlogging risk (for now it
  only words the warning: "clay soil drains slowly, which raises the risk", from the OpenLandMap
  topsoil texture class, also returned as `Soil.texture_class`; no score change).

## 2026-11-15 — Default data mode is `cached` (real data), with a committed demo snapshot
- **Decision:** `config/mvp.yaml` → `data_mode: cached` (was `mock`). `JsonCache` reads the runtime
  cache (`backend/.cache/`, gitignored) and then a **committed read-only snapshot**
  (`backend/app/cache/snapshots/`, `EnvSettings.cache_snapshot_dir`), as the `.gitignore` comment
  already anticipated. The snapshot holds the real responses for the demo points: San Carlos
  (11.0, −84.6) and Alajuela (10.0, −84.2), NASA POWER climate, OpenLandMap soil and NASA SMAP
  moisture (24 KB). `make cache-snapshot` copies newly fetched points into it.
- **Why:** The engine owner wants the API to serve real data always. With `mock` as default, anyone
  starting the server without `DATA_MODE` got fake climate and soil. `mock` stays for tests (they
  force it, with no snapshot).
- **Effect:** a fresh clone answers real data for the demo points; any other point answers
  `503 cache_miss` (never fake data) until someone with access fetches it in `live` mode.
- **Safety:** cache params never contain API keys (OpenTopography adds its key only at request
  time); `test_committed_snapshot_never_holds_secrets` checks every snapshot file.
- **Revisit if:** the frontend needs many arbitrary points (then a deployed `live` backend with keys).

## 2026-11-15 — Real soil in scoring: OpenLandMap pH + NASA SMAP monthly moisture
- **Decision:** In `live` and `cached` modes, `Sources.soil` is now `MeasuredSoil`
  (`openlandmap+nasa_smap`) instead of `MockSoil`:
  - **pH:** mean of the OpenLandMap layers at 0, 10 and 30 cm (Jeffry's `EarthEngineSoil`, reused).
  - **Moisture:** new adapter `smap.py`, NASA SMAP L4 `sm_rootzone` (0–100 cm, m³/m³) via Earth
    Engine: 12 monthly means of 2020–2024, one reading a day, mean within 15 km. See
    `docs/sources/smap.md`.
  - `SoilConditions` gains `moisture_monthly_m3m3`; seasons and sowing months are scored on the mean
    moisture of their own months (like rainfall). The scoring logic itself is unchanged.
- **Planting windows (agro-logic review 2026-11-15):** the "good month" rule now uses only the
  variables that change by month; soil pH is the same every month, so it's reported once per crop
  (`fixed_limits`) instead of vetoing all 12 months. A pH outside the crop's absolute range still
  leaves no window. `GOOD_SOWING_SCORE` stays 0.8 (the review found 0.7 gives the same windows).
- **API (additive):** `Soil.moisture_monthly_m3m3`, `CropPlanting.fixed_limits`; `is_good`
  description updated. New `data_gaps` lines say where pH and moisture come from.
- **Shared code:** Earth Engine error handling moved from `EarthEngineSoil.fetch_raw` to
  `openlandmap.call_earth_engine()`, used by both adapters.
- **Why:** The challenge is about NASA Earth observation; SMAP gives real moisture month by month,
  including the moisture left after the rains (Nov–Dec), which rainfall alone can't show.
  NASA POWER `GWETROOT` was the fallback (relative wetness, ~55 km, not m³/m³).
- **Effect:** Alajuela (example point): pH 6.4 and moisture 0.38–0.52 m³/m³, above the generic ideal
  (0.20–0.40), so rotation scores drop (e.g. 1.00 → 0.89). San Carlos: pH 5.4, moisture 0.21–0.36.
- **Open:** `GENERIC_SOIL_MOISTURE` is still one placeholder range for every crop and penalises wet
  areas; per-crop values need an `agro-logic` review. Demo points must be fetched once in `live`
  mode (~30 s each for SMAP) before `cached` mode works there.
- **Earth Engine project:** the team project `advance-topic-243700` (the default `GEE_PROJECT_ID`).
  Each teammate needs the IAM roles Service Usage Consumer and Earth Engine Resource Viewer on it.
- **Revisit if:**
  year-to-year variability (#34); per-crop moisture ranges.

## 2026-11-15 — Crop tolerance ranges imported from FAO EcoCrop (Adaptation Atlas copy)
- **Decision:** `scripts/import_ecocrop.py` copies the temperature, rainfall and pH ranges of our 5
  crops from the EcoCrop Parquet published by the Adaptation Atlas (CGIAR), picking each row by
  `ecoportcode` (rice 1574, beans 1668, maize 238663, sorghum 48747, cowpea 2153). It cites the code
  in `sources` and sets `verified=true`. The app still reads the CSV: no network at runtime.
- **What changed:** maize identical; rice and beans pH only; sorghum rainfall max 3000 → 700 mm and
  optimal temperature 27 → 22 °C; cowpea temperature, rainfall and pH. Rotation example scores
  unchanged; the "tolerance ranges are approximate" data gaps are gone.
- **`verified` now means** "tolerance ranges come from a cited source", which is what the API's data
  gap already said. Traits (nitrogen demand, mycorrhizal, …) stay labelled "team estimate".
- **Rainfall:** FAO defines these ranges as annual; the app keeps comparing them with rainfall over
  the crop cycle (decided 2026-11-06, confirmed in the planting-windows review). See
  `docs/sources/ecocrop.md`.
- **License:** the Adaptation Atlas catalog record lists CC-BY-SA-4.0; not confirmed for this file.
- **Not imported:** cycle min/max (too wide), killing temperature (mostly empty), soil and use fields.
- **Tooling:** `pyarrow` is an optional `data` extra, only for the script; app and tests don't need it.
- **Revisit if:** the license turns out different; crops are added (#24); a driest-month rainfall
  check is adopted.

## 2026-11-14 — Restore daily extrema (#85) and the recommendations contract test (#84)
- **Decision:** Re-apply the code, fixture, tests and docs of PRs #85 and #84 that the merge
  `9dc6b76` (main into `feat/planting-windows`, shipped with #86) dropped. Main still had the #85
  decision entry below, but `DAILY_PARAMETERS` was back to `T2M,PRECTOTCORR`, the San José fixture had
  no extrema and `tests/test_recommendations_contract.py` / `contract_validator()` were gone. The
  planting-windows (#86) and OpenLandMap (#87) changes are kept as they are.
- **Cache:** same as the #85 entry: daily requests are keyed by `T2M,T2M_MAX,T2M_MIN,PRECTOTCORR` again.
  Daily entries cached while main requested `T2M,PRECTOTCORR` have no extrema and sit under
  the old key. They are **not compatible** and are never served. In `cached` mode those points raise
  `cache_miss` until refetched once in `live` mode.
- **Why:** The #85 entry and `docs/indicators.md` described behavior main no longer had, and #41's
  contract coverage on the real POWER fixture had disappeared without anyone deciding to remove it.
- **Revisit if:** a future merge touches `nasa_power.py` or `tests/conftest.py`; check that these
  tests still exist.

## 2026-11-14 — Planting windows per crop from NASA POWER monthly climate
- **Decision:** `app/domain/planting_windows.py` scores each crop for every sowing month (Jan..Dec)
  over the months it spends in the field (cycle rounded up to whole months, wrapping the year), with
  the same `crop_season_fit()` used for rotations. Consecutive good months form a planting window.
  A month is good when the score is >= `GOOD_SOWING_SCORE` (0.8, placeholder) **and** no variable is
  below `MARGINAL_SCORE` (0.5).
- **Why:** The team asked when each crop can grow at a location. Calendars differ between regions; POWER
  monthly climate plus EcoCrop ranges answer it per point without a new dataset. Rotations keep the
  fixed seasons in `mvp.yaml`; windows are extra information and a check on those seasons.
- **Why the second condition:** the overall score averages climate, water and soil, so a crop whose
  cycle gets almost no rain (rainfall score 0.08) still scored 0.85. Requiring no marginal variable
  stops recommending those months. The same averaging affects rotation scores (flag for #27).
- **API:** `GET /planting-windows?lat=&lon=[&crops=]` (contract updated): per crop, the 12 sowing
  months with score, `is_good`, `limiting_factor` and variable scores, plus the windows. Uses the MVP
  priorities and variables. **Not yet:** monthly normals only, no year-to-year variability (#34).
- **Revisit if:** windows should drive the rotation seasons, or an agronomist suggests other thresholds.


## 2026-11-14 — Soil profile from OpenLandMap via Google Earth Engine
- **Decision:** New source: 7 OpenLandMap assets (pH, organic carbon, clay, sand, bulk density,
  field capacity at 33 kPa, USDA texture class) at 0, 10 and 30 cm, read with `earthengine-api`
  (new dependency) in **one** `reduceRegion` request per location, on the native ~232 m grid.
  `services.get_soil_data(latitude=, longitude=)` returns a JSON-ready dict (`SoilDataResult`) with
  units, attribution and depths. `silt_pct = 100 − clay − sand` only when both are valid and add up to
  100 % or less. Masked pixels give `None`. Field capacity is returned in m³/m³ (`field_capacity_m3m3`),
  the project's moisture unit, not in volumetric %. Config: `GEE_PROJECT_ID` (defaults to the team
  project `advance-topic-243700` in `settings.py`: an ID, not a secret), optional
  `GEE_SERVICE_ACCOUNT_KEY_FILE`. Each pixel is cached forever, in every mode (static maps).
- **Why:** The task asked for Earth Engine and these assets. Earth Engine was already set up for the
  team's project. One combined request is about 3 s, against 21 separate band reads. `ee` is imported
  lazily, because it takes ~0.6 s and mock or cached runs never need it.
- **Not changed:** `Sources.soil` / `MockSoil` (pH + moisture used for suitability scoring) and the
  API's `data_sources`. Feeding OpenLandMap pH into scoring changes recommendations, so it needs a team
  decision (and moisture still has no source).
- **Alternatives considered:** ISRIC SoilGrids REST API (no Earth Engine account, but beta and
  rate-limited); one request per asset (7 round trips).
- **Revisit if:** pH or texture should drive `soil` scoring; an endpoint is added (needs an
  api-contract.yaml change); we need 60–200 cm (the bands exist, add them to `DEPTHS_CM`).

## 2026-11-14 — NASA POWER daily adapter requests true daily max / min (T2.3, #19)
- **Decision:** The daily adapter now requests `T2M,T2M_MAX,T2M_MIN,PRECTOTCORR` and `parse_daily`
  returns `temperature_max_c` / `temperature_min_c` (°C, as POWER sends them). `field_indicators`
  already used those columns, so heat-stress and frost days are now real counts for POWER data.
  The San José fixture was refetched from the public API on 2026-11-14 with the four parameters;
  `T2M` and `PRECTOTCORR` are identical to the previous fixture. `parse_daily` also rejects a
  response whose declared `parameters.<P>.units` differ from `C` / `mm/day` (no conversion is done).
- **Why:** Heat-stress and frost days need the day's true extremes; the mean cannot show them.
  POWER provides them in the same request at no extra cost.
- **Cache:** the request string is the cache key, so daily entries cached before this change (key
  with `T2M,PRECTOTCORR`) are never served. They have no extrema. In `cached` mode those points
  raise `cache_miss` until refetched once in `live` mode. No daily cache is committed and demo
  responses are not cached yet (#18), so nothing shipped is affected.
- **Not changed:** `HEAT_STRESS_MAX_C = 35.0` stays a provisional generic placeholder (no
  `agro-logic` review, not crop-specific, not scored). No scoring constant or crop scoring changed.
  The mock daily source still has no extrema, so heat/frost stay `None` in `mock` mode.
- **Alternatives considered:** serving old cache entries under the legacy key (would silently mix
  responses with and without extrema); making extrema optional in `parse_daily` (a response that
  drops them would quietly turn real counts into `None`).
- **Revisit if:** demo fields are chosen and cached (#15, #18); the heat threshold gets an
  `agro-logic` review or crop-specific values; an endpoint exposes the table (#40).

## 2026-11-14 — Every strategy carries all five explanation parts (T4.4, #29)
- **Decision:** No contract change and no score change. `ranking.score_rotation()` now ends `risks`
  with two "Local review: …" items: (1) check sowing dates and varieties for each crop/season, since
  seasons are fixed calendar months from `mvp.yaml`; (2) what the score does not see: actual pest and
  disease pressure (only approximated by crop family in the #25 rules), field slope and erosion
  (`erosion.py` is not part of the ranking), irrigation (seasons are rainfed), labour and market prices.
  `benefits` says "No benefit found by the rotation rules and no strong climate, water or soil fit…"
  instead of being empty (possible for monoculture or same family with a weak fit). `data_gaps` always
  ends with "Scoring thresholds and rotation rule values are placeholders, not yet reviewed by an
  agronomist". `explanation` (why) and `evidence` were already always filled.
- **Why:** After #25, the top Alajuela strategy (maize → beans) still returned `risks: []`, so the
  issue's "risks for local review" part was missing and nothing told the farmer where a local expert is
  needed. With live data, verified crops and no generic variables, `data_gaps` could also be empty.
- **Left out on purpose:** a legume inoculant note (no source in the repo supports it for these crops
  and soils) and any list of individual rules in the no-benefit text (it would go stale as rules change).
- **Alternatives considered:** a new `local_review` field (needs a contract change agreed with the
  frontend; easy to split out later because every item starts with "Local review").
- **Review limits:** wording not yet reviewed by `agro-logic`, an agronomist or the frontend.
- **Revisit if:** the frontend wants local-review items as their own field, or an agronomist reviews
  the rules (then drop the placeholder gap).

## 2026-11-14 — Monthly field indicators from daily data; no heat/frost days from the daily mean (T2.3, #19)
- **Decision:** `app/domain/indicators.py` turns a daily series into one row per calendar month:
  mean temperature, rainfall total, dry days (< 1 mm), longest dry spell, extreme-rain days (>= 30 mm,
  same as erosion's `HEAVY_RAIN_MM`), heat-stress days (daily max >= 35 °C) and frost days (daily
  min <= 0 °C, = `FROST_C`). `services.field_indicators()` returns the table; no endpoint yet.
  Heat-stress and frost days are `None` unless the source gives true daily max / min. Missing days
  are skipped and counted per variable, end a dry spell, and an empty month gives `None`.
  Full rules: `docs/indicators.md`.
- **Why:** NASA POWER daily `T2M` is a daily mean and cannot show a hot afternoon or a frosty dawn,
  so counting heat or frost days from it would be a false claim. 1 mm is the ETCCDI wet-day
  threshold. Reusing 30 mm keeps the erosion and indicator counts consistent.
- **Placeholders:** `HEAT_STRESS_MAX_C = 35.0` (generic, needs an `agro-logic` review before scoring).
  `DRY_DAY_MM` and `HEAT_STRESS_MAX_C` are new; no existing scoring constant changed.
- **Alternatives considered:** estimating max/min from the monthly climatology or a fixed daily
  range (invented numbers); requesting `T2M_MAX`/`T2M_MIN` in the daily adapter now (needs a new real
  fixture and changes the daily cache key; left as a follow-up).
- **Open (issue #19 is not done):** (1) real data has no daily max / min yet, so heat-stress and
  frost days are always `None` for POWER; (2) the 35 °C heat threshold is unvalidated (no
  `agro-logic` review); (3) demo fields are not chosen (#15) and their daily responses are not
  cached (#18), so the only table is for the San José fixture.
- **Revisit if:** the daily adapter adds `T2M_MAX`/`T2M_MIN`; demo fields are chosen (#15); an
  endpoint exposes the table (#40).

## 2026-11-14 — Recommendations: representative point, no-baseline path, unsupported crops (T8.2, #41)
- **Decision:** No new fields. The contract now states what `POST /recommendations`
  already does: `lat`/`lon` (and every `Location`) are **one representative point**, never an area or
  polygon average; omitting `current_rotation` is the supported "no current crop" path (no baseline,
  `score_delta_vs_current` null); crop ids not in `GET /crops`, such as `pineapple` for the San Carlos
  walkthrough, fail with `unknown_crop` (422) and are never substituted. `unknown_crop` details now list
  each unknown id once (`["pineapple", "pineapple"]` used to report it twice). Description-only contract
  change; pending review by the frontend (#43) and contract owners.
- **Why:** The pilot demo selects an area on a map and assumes pineapple as current crop. Saying the
  boundaries in the contract keeps the frontend from labeling a point value as an area average or
  silently swapping pineapple for a configured crop.
- **Alternatives considered:** Accepting a bbox/polygon and averaging (needs a new contract, gridded
  data and sampling rules; out of MVP scope); adding pineapple now (traits, cycle and season fit are
  unvalidated, #24); adding a data-gap line to every response (changes responses and examples for a
  limitation the contract can state once).
- **Revisit if:** The team agrees an area input and point-selection rule, or pineapple is added to the
  catalog with sourced traits (#24).

## 2026-11-14 — Rotation rules with verdicts and reasons (T3.3, #25)
- **Decision:** `app/domain/rotation_rules.py` judges every consecutive crop pair (cyclic) and returns a
  verdict (favoured / allowed / discouraged), one reason per rule that fired, and a score adjustment.
  Rules: monoculture (−0.10, skips the others), same family (−0.05), family change (benefit, 0),
  legume after a non-legume (+0.05; stronger reason after a heavy feeder), **new** two heavy feeders in
  a row (−0.05), **new** non-host before a fungi-dependent crop (−0.05). Any risk → discouraged; else a
  scoring benefit → favoured; else allowed. "Heavy feeder" / "depends on fungi" = the trait's API word
  is `high` (`level_for`), so rules and API agree. `ranking.score_rotation()` now uses these rules.
  For two different crops the penalties are capped at `MAX_PAIR_PENALTY` (0.075), so changing crops
  always beats repeating one.
- **Choices (engine owner, marceconejo):** legume bonus kept for any non-legume (no score change);
  new rules get −0.05 placeholders, like same family; verdicts stay inside the domain (reasons already
  reach the API as `benefits` / `risks`, no contract change); rules never make a rotation non-viable.
- **`agro-logic` review (applied):** (1) cap added: rice → maize (same family + two heavy feeders) tied
  with maize monoculture; (2) rice `nitrogen_demand` 1 → 0.67: rainfed rice removes about as much
  nitrogen as sorghum, maize is the textbook heavy feeder; (3) reasons reworded to avoid overclaiming
  (beans fix little nitrogen and most leaves with the grain; same family shares *some* pests; a family
  change *helps* break cycles; monoculture builds up pests rather than "depleting the soil"). The
  reviewer cited references from memory (e.g. Giller 2001; Herridge et al. 2008), not checked yet.
- **Effect on the current 5 crops:** no score changes. Maize is the only heavy feeder now, so heavy after
  heavy can't fire (maize → maize is monoculture), and fungi break needs a non-host crop. Both stay ready
  for #24, which must add a non-host (see `docs/sources/ecocrop.md` to-do 5).
- **Alternatives considered:** bonus only after heavy feeders (lowers sorghum → legume); verdict-only
  rules with no score effect (left #27 without inputs); exposing verdicts in the API now (contract change
  better done with explanations #29); `HEAVY_AFTER_HEAVY_PENALTY = 0.03` instead of a cap (fixes only
  today's pair, not crops added later).
- **Open (team, not this PR):** the review warns that beans planted in primera (May–Aug) in humid
  San Carlos face heavy web blight; the regional bean season is around Nov–Dec. Check the season setup
  in `mvp.yaml` with a local source (MAG / INTA) before the demo.
- **Revisit if:** an agronomist disagrees with a rule or value; #29 needs per-transition verdicts in the
  response; sorghum joins the MVP crops (closer-relative penalty, slow start after sorghum).

## 2026-11-14 — Crop schema v1: soil-health, nutrition and market traits (T3.1, #23)
- **Decision:** `data/ecocrop_subset.csv` gains `root_depth_m`, `is_cover_crop`, `forage_value`,
  `nutrition_density`, `mycorrhizal_affinity`, `nitrogen_demand`, `market_note` and `sources`. The four
  trait columns are 0..1 scores; the API sends each as `{"level": none|low|medium|high, "score": 0..1}`
  (`TraitValue`), so the frontend can show the word and the number on hover. The `Trait` API type
  builds it from the score (`level_for()`), and `tests/test_trait_levels.py` fails if any response
  declares a trait any other way. The loader rejects bad values at startup.
  `nitrogen_demand` and `sources` were added beyond the issue's list: rule #25 needs "heavy feeders"
  and #24 needs a citation per crop. Full spec: `docs/crop-schema.md`.
- **Why:** Rotation rules, badges and explanations need these traits, and keeping them in the CSV keeps
  crop knowledge out of Python.
- **Data status:** root depth from FAO-56 Table 22; the other traits are a team estimate, labelled as
  such in `sources`, until #24 cites them. Every row stays `verified=false`.
- **Alternatives considered:** words only in the data (scoring would need its own mapping); words only
  in the API (no number for a hover); separate `*_score` fields or a score map next to the words (the
  pair can drift apart); a separate trait file (two files to keep in sync).
- **Contract change:** `Crop` gains the same 8 fields, all required, and a new `TraitValue` schema. There
  is no frontend yet, so nothing breaks; review it with the frontend when it starts.
- **Also decided:** keep `nitrogen_demand`, keep the CSV name, leave long-cycle crops out of #24.
- **Revisit if:** #24 finds cited numeric values that need finer cutoffs than `LOW_BELOW` / `MEDIUM_BELOW`.

## 2026-11-14 — mypy follows the running interpreter (no `python_version` pin)
- **Decision:** Removed `python_version = "3.11"` from `[tool.mypy]`.
- **Why:** numpy 2.5 (pulled in by pandas) ships stubs with 3.12-only syntax, so a 3.12 venv failed `make lint`
  with "Type statement is only supported in Python 3.12 and greater". CI stays on 3.11 and resolves an older numpy.
- **Alternatives considered:** Pin `python_version = "3.12"` (misstates the supported minimum); cap numpy.
- **Revisit if:** CI and local Python versions diverge enough to give different mypy results.

## 2026-11-14 — Erosion risk from SRTM slope + NASA POWER daily rain
- **Decision:** New source OpenTopography `/v1/elevation`, dataset `SRTM_GL1`, key `OPEN_TOPOGRAPHY_KEY`.
  Slope from the point + its 4 direct neighbours (one SRTM sample, ~30 m) by central differences.
  Terrain risk: < 5 % low, 5–15 % medium, > 15 % high. Rainfall risk = worse of average mm/day and
  heavy days (≥ 30 mm) per 30 days (`RainfallThresholds`, overridable per call). The wettest day
  (`max_daily_rainfall_mm`) is reported but **not scored**. Combined = terrain, raised one step only
  when rain is high; never below terrain. **Medium rain never changes the result, on purpose.**
  `services.erosion_risk()` returns `ErosionRiskResult` (TypedDict, 8 fields); no endpoint yet.
  Mock sources (`MockTerrain`, `MockClimate.daily_weather`) and `Sources.daily` / `Sources.terrain`
  are wired in `build_sources()`; `Sources.names()` (the API's `data_sources`) is unchanged.
- **Why:** The free key allows 50 calls/day and the API returns one point per call: 5 calls per
  location instead of 9 for a 3×3 grid. SRTM never changes, so cached points are reused even in
  `live` mode (`JsonCache.peek()`; `get_or_fetch` and NASA POWER are unchanged). Rates instead of
  totals make short and long periods comparable; the wettest day keeps growing with the period, so
  a full year would almost always score high. Normal Costa Rican wet-season rain is "medium", so only
  clearly heavy rain may move a slope class. Flat land with heavy rain is not high water-erosion risk.
- **Known limits (review 2026-11-14):** hard cut-offs (3.99 vs 4.0 mm/day flips the class); over short
  periods one storm moves the heavy-day rate a lot (1 heavy day in 10 days = high). POWER's ~0.5° grid
  (~55 km) averages local convective storms, so **heavy days and the wettest day are underestimated**
  compared with a rain gauge; treat the rain risk as a regional signal, not a field measurement.
- **Alternatives considered:** 3×3 grid with Horn's method (9 calls); `/globaldem` AAIGrid tile
  (1 call, but a different endpoint than the spec); RUSLE (needs soil erodibility and cover data we
  don't have); scoring the wettest day only for periods ≤ 31 days; medium rain raising medium slopes.
- **Revisit if:** `agro-logic` review of the thresholds; a finer rain source (e.g. GPM IMERG, ~10 km)
  for storm counts; a soil source becomes available.

## 2026-11-14 — pandas for daily NASA POWER data
- **Decision:** Add `pandas>=2.2` (and `pandas-stubs` for mypy) to the backend. The new
  `NasaPowerClimate.daily_weather()` returns a DataFrame (`date`, `temperature_c`, `rainfall_mm`).
  Daily fill values become NaN instead of rejecting the whole request.
- **Why:** Data retrieval and calculations (dry spells, heat waves, frost days, aggregations) are
  easier and clearer in pandas, which the team's data work already uses.
- **Alternatives considered:** Plain tuples in a frozen dataclass, like `MonthlyClimate` (no extra
  dependency, but every calculation is hand-written).
- **Revisit if:** `make setup` gets too slow, or the domain layer needs to stay pandas-free
  (convert DataFrames to domain models in `services.py` before they reach `app/domain/`).

## 2026-11-14 — Frontend mock data = generated example responses (T1.2, #13)
- **Decision:** `docs/examples/*.json` hold real responses for one demo field (Alajuela, lat 10.0,
  lon −84.2), generated by `scripts/make_examples.py` from the app in `cached` mode on top of the NASA
  POWER fixture. `tests/test_examples.py` validates every file against the contract schemas.
- **Why:** The frontend can build against realistic data without running the backend, and the mock can't
  silently drift from the contract. Hand-written mocks would.
  The test also regenerates the examples in memory and fails if the committed files differ
  (`generated_at` is pinned so output is deterministic), and checks `format` keywords.
- **Tooling:** `backend/scripts/` is the home for dev scripts. It is type-checked by mypy and importable
  in tests (`pythonpath = ["."]`). New dev dependency `jsonschema>=4.18,<5` (already pulled in transitively).
- **Alternatives considered:** Hand-written JSON (drifts); `mock` mode output (fake climate, less realistic).
- **Revisit if:** The demo fields change (T1.4) or the frontend wants more fields than one.

## 2026-11-14 — Contract v0.2: compare against the farmer's current rotation, structured explanations
- **Decision:** `POST /recommendations` takes an optional `current_rotation` (one crop id per season).
  It is scored like every other combination and returned as `current_rotation` (its `rank` is its
  position among all combinations, so it can exceed `top_n`). Its crops join the candidate set.
  Every `Rotation` gains `is_current`, `score_delta_vs_current`, `benefits`, `risks`, `data_gaps` and
  `evidence`. `notes` is kept but deprecated (= benefits + risks). New error code `invalid_rotation`
  (422) when the length doesn't match the seasons. `MonthClimate` / `SeasonSummary` gain
  `temperature_max_c` / `temperature_min_c`. Additive only; `method_version` is now `suitability-v1`.
- **Why:** The challenge asks to compare at least three strategies *including the existing rotation*
  and to explain for each why it was suggested, the evidence, benefits, information gaps and risks.
- **Alternatives considered:** Replacing `notes` (breaks the frontend); letting the frontend find the
  baseline with `top_n=50` (fails when the farmer's crops aren't in `crops`).
- **Revisit if:** The frontend no longer reads `notes` (remove it), or seasons become configurable per request.

## 2026-11-14 — Same-family penalty in rotation scoring
- **Decision:** `SAME_FAMILY_PENALTY = 0.05` per transition between *different* crops of the same
  botanical family (e.g. rice → maize, both Poaceae), half of `MONOCULTURE_PENALTY` (0.10).
  A family change is listed as a benefit.
- **Why:** Crops of the same family share most pests and diseases, so the cycle isn't broken. Before
  this, rice → maize scored like a real rotation. Placeholder value, pending `agro-logic` review.
- **Revisit if:** An agronomist suggests per-family values, or pest data becomes available.

## 2026-11-14 — Heat stress and frost risk variables (mvp.yaml: variables)
- **Decision:** `heat` and `frost` added to `variables` in `mvp.yaml`, both in the climate category,
  using POWER `T2M_MAX` / `T2M_MIN` (monthly means of daily max/min), which were already fetched.
  - heat: season mean daily max vs the crop's absolute max temperature. 1 at or below it, linear to 0
    at `abs_max + HEAT_MARGIN_C` (6 °C).
  - frost: daily min of the season's coldest month. 0 at or below 0 °C, 1 from 5 °C (generic, all crops).
- **Why:** The challenge names heat stress and frost risk. No extra requests; cached data still works.
- **Alternatives considered:** Counting hot/frost days from daily POWER data (more requests, more
  accurate); per-crop frost limits (no reliable source yet).
- **Revisit if:** `agro-logic` review, or the pilot region includes highlands where frost matters.
  Frost scores 1 almost everywhere in lowland Costa Rica.

## 2026-11-07 — Project-wide error guide, enforced
- **Decision:** `docs/errors.md` is mandatory. One catalog (`app/errors.py`: `ErrorCode` + classes),
  one HTTP translator (`app/api/errors.py`), one response envelope for every error
  (`{"error": {code, message, details, request_id}}`) plus the `X-Request-ID` header. Errors are logged once at the boundary.
- **Enforced by:** `tests/test_error_policy.py` (only catalog errors raised, no exception classes elsewhere,
  no hand-built error responses, codes ↔ HTTP status ↔ guide ↔ contract ↔ tests in sync, every route documents errors),
  `tests/test_errors.py` (every reachable code through the real app), ruff `BLE`, `TRY`, `S101`, `S110`, `S112`, `G`, `LOG`.
- **Why:** The frontend gets one predictable shape and switches on stable codes. Bugs are traceable by request id.
  Messages can't leak secrets or internals.
- **Contract change:** `ErrorResponse` was `{detail}`; now the envelope + `ErrorBody` + `ErrorCode` enum.
  Still draft v0, so it needs the frontend's review.

## 2026-11-06 — Stricter code quality tooling and per-folder rules
- **Decision:** ruff now also runs `N, C4, RET, PTH, DTZ, T20, ANN, PT, PL, RUF`; mypy `--strict`
  (pydantic plugin) on `app/` in `make lint`, pre-commit and CI; `tests/test_architecture.py` enforces
  layer imports. Each main folder has an `AGENTS.md` (+ `CLAUDE.md` importing it).
- **Why:** Rules checked by tools hold for every teammate and AI assistant. Prose alone drifts.
- **Changes it forced:** `CacheMiss` → `CacheMissError`, `InvalidRequest` → `InvalidRequestError`,
  `rank_rotations` is keyword-only.

## 2026-11-06 — Soil stays mocked in v0
- **Decision:** `SoilSource` uses `MockSoil` in every `data_mode`. Responses say so in `data_sources.soil = "mock"`.
- **Why:** No soil source has been chosen yet. Candidates: NASA SMAP for surface moisture
  (needs an Earthdata login and has coarse resolution) and ISRIC SoilGrids for pH (not NASA, but free REST API).
- **Revisit if:** the soil source evaluation is done. Use `/new-source` or the README steps.

## 2026-11-06 — Scoring method v0 (EcoCrop-style trapezoids)
- **Decision:** Per variable 0..1 trapezoid over EcoCrop ranges, grouped as climate (temperature),
  water (rainfall, soil moisture), soil (pH); priority-weighted mean; 0 if any variable is outside
  its absolute range. Rotation = one crop per season, cyclic; −0.10 for monoculture, +0.05 for legume
  after non-legume (split across transitions).
- **Why:** Simple, explainable to farmers and judges, and works with the few variables we have.
- **Known simplifications:** mean temperature only (no heat/frost days); crop-cycle rainfall = mean
  monthly season rainfall × cycle length; one generic soil-moisture range for every crop; bonus and
  penalty values are placeholders.
- **Revisit if:** The `agro-logic` review or an agronomist flags issues; when T2M_MAX/T2M_MIN are used.

## 2026-11-06 — Default seasons: primera (May to Aug) and postrera (Sep to Nov)
- **Decision:** Two rainfed seasons, dry season treated as fallow.
- **Why:** Standard Central American rainfed calendar; a rainfed dry-season crop fails on water in most
  of the Pacific slope, so every rotation would come out non-viable.
- **Revisit if:** The pilot region is on the Caribbean slope (no marked dry season) or irrigation is in scope.

## 2026-11-06 — NASA POWER climatology endpoint for temperature and rainfall
- **Decision:** Use `/api/temporal/climatology/point` (monthly normals 2001–2025, `AG` community)
  instead of daily data.
- **Why:** One small request per location (~1.5 KB), already aggregated to the monthly level the
  model uses. No API key. Daily data can be added later for extremes (heat days, dry spells).

## 2026-11-06 — Crop data as a local EcoCrop subset CSV
- **Decision:** `data/ecocrop_subset.csv`, versioned. Values marked `verified=false` until checked
  against the FAO EcoCrop source.
- **Why:** EcoCrop has no stable API, the data is small and static, and the demo must not depend on it.

## 2026-11-06 — Contract-first API with a CI check
- **Decision:** `docs/api-contract.yaml` is the agreement with the frontend. `tests/test_contract.py`
  fails if the app and the contract differ (endpoints, schema names, fields, required, params).
- **Why:** Frontend and backend work in parallel. Drift shows up in CI instead of at demo time.
- **Status:** Draft v0, still to be reviewed with the frontend.

## 2026-11-06 — Data modes: mock / live / cached
- **Decision:** `data_mode` in `config/mvp.yaml` (env `DATA_MODE` overrides). `live` writes every
  response to `backend/.cache/`; `cached` never touches the network. `live` falls back to the cache
  when a source fails.
- **Why:** The frontend gets realistic data from day 1, and the demo survives bad venue Wi-Fi.

## 2026-11-06 — Stack and tooling
- **Decision:** Python ≥ 3.11, FastAPI, Pydantic v2, httpx. venv + pip via `make setup`. ruff for
  lint and format, pytest, pre-commit, GitHub Actions.
- **Why:** The team knows Python and pandas. venv + pip needs no extra tool (team choice over uv).

## 2026-11-06 — Backend is self-contained in `backend/`
- **Decision:** All backend code, config, docs and its `pyproject.toml` live under `backend/`.
- **Why:** The frontend's location (same repo or separate) is still undecided. This way either option works.
