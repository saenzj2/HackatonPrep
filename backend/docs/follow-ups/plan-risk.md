# Plan: `POST /plan-risk`, "when could this plan fail?"

> **Owner:** Marce, who owns the engine and decides this contract.
> **Status (2026-11-15):** phases 1–6 done (contract, daily history, engine + agro-logic review,
> actions and alternatives, endpoint wired to real data, El Niño with NOAA RONI). Open questions in §5 answered, history
> range fixed to 2000-06-01 → 2025-12-31, demo point relabeled Los Chiles (see
> `docs/decisions.md`). Phase 7: cache snapshot committed-ready and `/demo-check` green;
> `farmer-language` review in progress; code review, commit and PR by the engine owner.
> **For:** the coding agent implementing it.
>
> Work phase by phase. Stop for Marce's approval where it says **STOP**. Leave every change
> uncommitted: Marce commits. Run `make check` at the end of every phase.

## 1. Goal
Pitch: *"Most tools help farmers decide what to plant next. Guardians of the Harvest helps them
understand when their plan might fail, and what they can do before it does."*

The farmer gives a point and a plan (crop + sowing date). The backend replays that plan against
every past year of real NASA daily weather at that point, and answers:
- **How often it would have failed and why:** "4 of 24 years: harvest rain in 3, dry spell at
  flowering in 1".
- **Which years:** e.g. 2020 (Eta/Iota). Farmers remember those years, which builds trust.
- **What to do:** actions per cause, plus alternatives that failed less often (sow 2 weeks
  earlier, another crop).
- **El Niño context:** failures in El Niño years vs the rest, and the current ENSO phase.

**Reference:** ARM Online (APSIM, Australia), https://armonline.net.au/ra.

**What is new here:** one farmer's plan, Costa Rica's calendar, NASA data, Spanish.

**What is NOT in scope:**
- crop growth models or yield numbers;
- seasonal forecasts;
- irrigation scheduling;
- rotations. Each planting is evaluated alone; a plan with two plantings returns two results.

## 2. Ground rules
Read these first:
- root `AGENTS.md`, `backend/AGENTS.md` and the `AGENTS.md` of each folder you touch;
- `backend/docs/errors.md`;
- `.claude/skills/new-endpoint/SKILL.md`.

Rules:
- **Data mode:** run the server and checks with `DATA_MODE=cached`, always set explicitly.
  - Live calls to NASA POWER, NOAA and Earth Engine are allowed when you need them.
  - Never call OpenTopography (this feature doesn't need it).
  - Never read `.env`.
- **Domain code is pure and stdlib only.** `app/domain/` doesn't import pandas, as in
  `indicators.py`. The adapter returns pandas or raw data, and `services.py` converts it to frozen
  dataclasses of tuples before calling the domain.
- **Farmer-facing text is bilingual** with `Text(en, es)` from `app/domain/text.py`:
  - Spanish months, decimal comma;
  - crop articles from `CropProfile.the_es` / `of_the_es`;
  - the API returns `LocalizedText`.
- **Every threshold is a named module constant**, commented as a placeholder or with its source,
  and listed in `docs/decisions.md`. Add the new ones to the "Scoring constants" list in
  `backend/AGENTS.md`.
- **Coordinate with Jeffry, who works on the climate/soil/erosion endpoints and the cache grid:**
  - Don't change `daily_weather()`, `DAILY_PARAMETERS` or `daily_request_params()` in
    `nasa_power.py`. Changing the parameter tuple changes the cache key of his daily data.
  - Add a separate method and cache namespace instead (phase 2).
- **Tests:**
  - Tests never use the network; use fixtures and `respx`.
  - Add one `@pytest.mark.network` test per new source.
  - Add an HTTP test for every error path.

## 3. Proposed contract (phase 1, needs Marce's OK)
This is a draft. Adjust names to match `api-contract.yaml` style (snake_case, unit suffixes,
`LocalizedText` for farmer text).

```yaml
POST /plan-risk
request: PlanRiskRequest
  lat: number                  # same bounds/validation as /recommendations
  lon: number
  plantings:                   # 1..4
    - crop: string             # crop id from GET /crops
      sowing_month: int        # 1..12
      sowing_day: int          # 1..31, default 1 (validated against the month)
response: PlanRiskResponse
  location: {lat, lon}
  years_evaluated: {first: int, last: int, count: int}   # complete seasons only
  data_sources: [string]
  enso_now: {oni: number, phase: el_nino|la_nina|neutral, season: "ASO 2026", source: string} | null
  plantings:
    - crop_id, crop_name: LocalizedText, sowing_date: "MM-DD", harvest_date: "MM-DD"
      failed_years: int; failure_rate: number (0..1)
      summary: LocalizedText                  # "Would have failed 4 of 24 years, mostly harvest rain"
      causes:                                  # sorted by count, only causes seen at least once
        - cause: late_dry_start|flowering_dry_spell|cycle_rain_low|cycle_rain_high|harvest_wet|flowering_heat
          severity: fail|stress
          years: [int]
          count: int
          explanation: LocalizedText          # what happened, with the numbers of the worst year
          actions: [LocalizedText]
      years: [{year, outcome: ok|stress|fail, causes: [cause], enso: el_nino|la_nina|neutral|null}]
      enso_split: {el_nino: {years, failed}, la_nina: {...}, neutral: {...}, note: LocalizedText} | null
      alternatives:                            # at most 3, each better than the plan
        - kind: shift_sowing|other_crop
          crop_id, sowing_date, failed_years, failure_rate
          label: LocalizedText                 # "Sow 2 weeks earlier (Aug 18): fails 1 of 24 years"
  data_gaps: [LocalizedText]
errors: validation_failed, out_of_region, unknown_crop (422); source_unavailable, source_bad_data
  (502); cache_miss (503). New only if needed, e.g. not_enough_history (422 or 503, see errors.md).
```

**STOP:** show this to Marce as a short YAML snippet and wait for approval before editing the
contract.

## 4. Phases

### Phase 1: contract
1. Get Marce's approval on section 3.
2. Edit `docs/api-contract.yaml`. Add the schemas in `app/api/schemas.py` with class names equal to
   the component names and `extra="forbid"`.
3. Add the route in `app/api/routes.py` returning a fixed, realistic example from `services.py`.
   That way the frontend can start right away; this mirrors how #13 mock responses were done.
4. `test_contract.py` passes. Add a request to the Bruno collection (`docs/bruno/`).

### Phase 2: daily history per point (data)
Add a new method to `NasaPowerClimate`:

```python
daily_history(*, lat, lon, start, end) -> pd.DataFrame
```

- **Parameters:**
  - `IMERG_PRECTOT`: GPM IMERG satellite rain, ~0.1°;
  - `PRECTOTCORR`;
  - `T2M_MAX`, `T2M_MIN`;
  - `GWETROOT`: root-zone wetness, 0..1.
- **Cache:** its own namespace `nasa_power_daily_history` and its own params builder.
- **Verify against a real live response, then write the result in `docs/sources/nasa_power.md`:**
  - the IMERG units;
  - that `IMERG_PRECTOT` needs `time-standard=UTC`, or the API errors or returns fill values;
  - the first IMERG date (expected June 2000);
  - the latency (expected ~2 months);
  - fill values (−999);
  - the `GWETROOT` units.
- **Range:** one request for 2000-06-01 → the last complete month. The rain-probe script fetched
  35 years in one call.
- **Validate before caching**, like `_fetch_valid_daily`: units check, fill values → NaN.
  Reject only if a whole column is empty.
- **Fixture:** save a trimmed real response, a few months of San Carlos (11.0, −84.6), in
  `tests/fixtures/nasa_power/`.
- **Tests:**
  - parse the fixture;
  - live → cached, fallback and miss with `respx`;
  - one network test.

**Rain source decision (log it in `decisions.md`):**
- Use IMERG for rain. Only seasons that IMERG fully covers are evaluated (2001 → last complete
  season, ~24 years).
- MERRA-2 `PRECTOTCORR` underestimates tropical rain and undercounts dry spells. Keep it only to
  report in `data_gaps` how far it differs from IMERG.
- Don't mix sources across years.

### Phase 3: stress-test engine (`app/domain/plan_risk.py`, pure)
**Inputs:**
- `DailyHistory`, a frozen dataclass of the date tuple plus `rain_mm`, `tmax_c`, `tmin_c`,
  `root_wetness`; NaN allowed;
- a `CropProfile`;
- the sowing month and day.

**Season mechanics:**
- Season year = the year of sowing.
- Harvest = sowing + `cycle_days`. Seasons that cross the new year (Nov/Dec sowing) are fine.
- A season counts only if all its days are in the history and less than 10% of its rain days
  are NaN.
- Under 10 valid seasons: don't raise from the domain (that isn't a code bug). Return a result
  flagged `not_enough_history` and let the service turn it into whatever Marce picks (open
  question 3).

**Stage windows:** fractions of `cycle_days`, placeholder constants for the `agro-logic` review.
- Establishment: days 0–20.
- Flowering: 45%–65% of the cycle.
- Harvest: the last 15 days.

**Checks per season.** Each one is a small pure function returning `(severity | None, numbers)`.

| Cause | Rule (placeholders) | Severity |
|---|---|---|
| `late_dry_start` | rain in establishment < 30 mm, or a dry run of ≥ 7 days (< 1 mm/day) in it | stress; fail if < 10 mm |
| `flowering_dry_spell` | longest dry run in flowering ≥ 10 days | stress; fail if ≥ 15 days, or ≥ 10 days with mean `GWETROOT` < 0.5 |
| `cycle_rain_low` / `cycle_rain_high` | cycle total outside `rainfall_mm.opt_*` | stress; fail outside `abs_*` |
| `harvest_wet` | harvest-window rain ≥ 150 mm, or mean `GWETROOT` ≥ 0.85 for crops with `needs_good_drainage` | stress; fail ≥ 250 mm |
| `flowering_heat` | days in flowering with `tmax_c` > `temperature_c.abs_max` (reuse suitability's heat definition and `HEAT_MARGIN_C` if it applies) | stress ≥ 5 days; fail ≥ 10 days |

**Outcome per year:** `fail` if any check fails, else `stress` if any is stressed, else `ok`.
`failure_rate` = failed / evaluated.

**Sanity check against the San Carlos probe** (`risk_probe.py` in Marce's session, MERRA-2 rain,
1991–2025):
- maize sown May 15 and beans sown Sep 1 should show:
  - late or dry starts in a sizeable share of years (rains started after May 15 in 12 of 35);
  - beans harvest rain or waterlogging in 2020 (Eta/Iota, ~1000 mm in November) and in 2024.
- IMERG numbers will differ. Explain any large gap rather than tuning to match.

**Tests:** a synthetic `DailyHistory` per check (just below and just above each threshold), year
crossing, NaN handling, and the outcome aggregation.

### Phase 4: actions and alternatives
**Actions:** `ACTIONS: dict[Cause, tuple[Text, ...]]` in `app/domain/plan_risk.py`, or a sibling
module.
- Two or three concrete actions per cause, e.g.:
  - harvest rain → "plan to harvest earlier / dry the grain under cover";
  - waterlogging → raised beds (lomillos) and drainage;
  - dry flowering → sow earlier, an early variety, mulch;
  - heat → shift the date.
- Mention INS crop insurance only as "ask about…", with no claims about coverage.
- Every action needs a source, recorded in a comment and in `decisions.md`. The `fact-checker`
  verifies them in phase 7.

**Alternatives (pure, reuse the engine):**
- Re-run with the sowing date shifted −28, −14, +14 and +28 days.
- Re-run every other MVP crop (`mvp.yaml` `crops`) on the same date.
- Keep options that fail in fewer years than the plan. Rank by `failed_years`, then by shift size.
  Return at most 3.

### Phase 5: wire the endpoint
`services.plan_risk(ctx, req)`:
- validate the point and the crops (reuse `check_location` / `resolve_crops`);
- fetch the history, convert to `DailyHistory`;
- run the engine, add actions and alternatives, build the schemas.

Text and data:
- `summary` and `explanation` texts quote the worst year's numbers with units ("2020: 312 mm in
  the last 15 days").
- `data_gaps` must cover, bilingual:
  - satellite rain over a ~10 km cell, not the farm;
  - root wetness from a model, ~50 km;
  - the years covered;
  - no yields, just weather patterns.

Tests and docs:
- happy path in `tests/test_api.py`;
- every error path in `tests/test_errors.py`;
- update `docs/frontend-guide.md` with a section showing a real response;
- update the Bruno request.

### Phase 6: El Niño (ENSO)
**New source:** the NOAA CPC ONI table (`https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt`,
plain text).
- Run `/explore-dataset` first, then `/new-source`.
- Adapter `app/integrations/noaa_oni.py`, with a `parse_oni` function to test and its own cache
  namespace.
- The cache key should change monthly (e.g. include the current year-month) so live mode refreshes
  it.

**Year labels** (placeholder rule, in `decisions.md`):
- `el_nino` if ONI ≥ +0.5 in the 3-month season covering the sowing month;
- `la_nina` if ≤ −0.5;
- otherwise `neutral`.

**Split:**
- Report failures per phase with their `n`.
- If a phase has fewer than 4 years, the note says there's too little data to compare. Never
  claim significance.

**`enso_now`:** the last ONI value and its phase.
- Latest known: ASO 2026 +2.46, strong El Niño. Read it from the data, never hardcode it.
- Don't assume El Niño means drought at the point: San Carlos is a transition zone between the
  Caribbean and Pacific regimes. Report what the point's own history shows.

**If NOAA is down in live mode** → cached fallback, as for every source. The whole ENSO block is
optional in the response (`null`) only if the contract says so.

### Phase 7: validation and demo
- **Reviews, then a `decisions.md` entry listing what changed:**
  - `agro-logic` agent: stage windows, thresholds, actions;
  - `fact-checker`: every action source and data claim;
  - `farmer-language`: every `es`/`en` text.
- **Demo data:**
  - fetch San Carlos (11.0, −84.6) and Alajuela (10.0, −84.2) live once;
  - run `make cache-snapshot` (ask Marce before it changes committed files);
  - run `/demo-check`.
- **Final:** `make check`, then the `reviewer` agent on the diff, then hand back to Marce with a
  short summary, the open questions and a PR description draft.

### Stretch (only if everything above is done): "how is this season going?"
- **SMAP:** add the `sm_rootzone_pctl` band to `app/integrations/smap.py`. Recent root-zone
  percentile vs 2015+ history: "drier than 8 of 10 years for this date".
- **Rain:** IMERG rain to date this season vs the same period in past years (respect the ~2-month
  latency and say the data date).
- Separate contract field or endpoint: ask Marce.

## 5. Open questions for Marce
1. Plantings per request: is 1–4 OK? Should we also accept a season name (`primera`/`postrera`)
   instead of a date?
2. Should alternatives include crops outside `mvp.yaml` (the 5 catalog crops)?
3. `not_enough_history`: is it a new error code, or a 200 with a data gap?
4. Is ENSO part of the MVP, or the first thing to cut if time runs short? Suggested cut order:
   stretch → ENSO split → alternatives.

## 6. References
- `app/integrations/nasa_power.py`: `daily_weather` and `parse_daily`, the pattern for the new
  method.
- `app/domain/planting_windows.py`: how cycle windows and dry-month checks work today (monthly
  climatology).
- `app/domain/suitability.py`: heat, waterlogging (`needs_good_drainage`, wetness 0.80–0.95).
- `app/domain/indicators.py`: daily-data domain code without pandas.
- `docs/follow-ups/farmer-texts-and-facts.md`: text conventions and open agronomy questions (Zona
  Norte bean calendar, web blight at harvest).
- `docs/sources/nasa_power.md`, `docs/sources/smap.md`.
