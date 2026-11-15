# Frontend guide: how to use the Guardians of the Harvest API

> **Who this is for:** whoever builds the farmer-facing app. It explains every endpoint, every field,
> what each value means, real example responses, error handling, and **how we recommend showing each
> piece** to a farmer or a judge. Source of truth for shapes: [`api-contract.yaml`](api-contract.yaml)
> (CI fails if the backend drifts from it). Design proposals (screens, journey) live in
> [`docs/frontend-requirements-proposal.md`](../../docs/frontend-requirements-proposal.md); this guide
> describes **what the backend does today**.
>
> Examples below are real responses for **San Carlos, Alajuela (lat 11.0, lon −84.6)** in `cached`
> mode, trimmed with `…` where long. Full, always-valid examples: [`docs/examples/`](examples/README.md).

---

## Contents
1. [Quick start](#1-quick-start)
2. [Conventions you'll see everywhere](#2-conventions-youll-see-everywhere)
3. [Endpoints](#3-endpoints)
   - [GET /health](#get-health) · [GET /crops](#get-crops) · [GET /conditions](#get-conditions) ·
     [GET /planting-windows](#get-planting-windows) · [POST /recommendations](#post-recommendations)
4. [Errors](#4-errors)
5. [How to display it (UI recommendations)](#5-how-to-display-it-ui-recommendations)
6. [Label maps (English / Spanish)](#6-label-maps-english--spanish)
7. [TypeScript types](#7-typescript-types)
8. [Known gaps and gotchas](#8-known-gaps-and-gotchas)
9. [Where things live](#9-where-things-live)

---

## 1. Quick start

```bash
make setup      # once: Python venv + dependencies (from the repo root)
make dev        # API on http://localhost:8000
```

| What | Where |
|---|---|
| Base URL (local) | `http://localhost:8000` |
| Interactive docs (try requests in the browser) | `http://localhost:8000/docs` |
| OpenAPI JSON (generate a client from it) | `http://localhost:8000/openapi.json` |
| Ready-made requests (Bruno / Postman) | [`docs/bruno/`](bruno/README.md) |
| Allowed browser origins (CORS) | `http://localhost:3000`, `http://localhost:5173`. Other ports: set `CORS_ORIGINS` in `backend/.env` (comma-separated) and restart |

**Data is real and offline by default.** The backend runs in `cached` mode: it answers from saved
real data (NASA POWER climate, OpenLandMap soil, NASA SMAP moisture, FAO EcoCrop crops) and never
calls the internet. A committed snapshot covers the **two demo points**:

| Demo point | lat | lon |
|---|---|---|
| **San Carlos** (pilot) | `11.0` | `-84.6` |
| Alajuela (test point) | `10.0` | `-84.2` |

Any other point inside the region answers **`503 cache_miss`** (see [Errors](#4-errors)), never fake
data. To demo a new point, ask the backend team to fetch it once (`live` mode) and commit it.
**Send the demo coordinates exactly** (`11.0`, `-84.6`): climate and moisture are matched to 2
decimals, but the soil map uses 250 m pixels, so a pin a few metres away (e.g. 11.001, −84.601)
can land in another pixel and answer `cache_miss`. When the user drops a pin near a demo point,
snap it to the demo point and say so ("Using the nearest demo location").

The region accepted at all: bounding box `[min_lon, min_lat, max_lon, max_lat] = [-86.0, 8.0, -82.5,
11.3]` (Costa Rica). Outside it: `422 out_of_region`. Get it at runtime from `GET /health`.

---

## 2. Conventions you'll see everywhere

### Farmer text is bilingual: `{ "en": "...", "es": "..." }`
Every sentence meant for a person (explanations, benefits, risks, data gaps, evidence, notes) is a
**`LocalizedText`** object. Pick the user's language; never translate on your side, never concatenate
them. Spanish is already written for Costa Rica (frijol, maíz, primera, postrera, "setiembre"),
with a decimal comma.

```json
{ "en": "Maize (primera) → Common bean (postrera): changing crop family cuts pest cycles, …",
  "es": "Maíz (primera) → Frijol (postrera): cambiar de familia corta plagas, …" }
```

```ts
const t = (x: LocalizedText, lang: "en" | "es") => x[lang];
```

**Not bilingual (yet):** error `message`s (English; use the error `code` to show your own text),
`crop_name` inside rotations and planting windows, and `Crop.market_note`. See
[Known gaps](#8-known-gaps-and-gotchas) for workarounds.

### Units (always in the field name or description)
| Quantity | Unit | Examples |
|---|---|---|
| Temperature | °C | `temperature_c`, `temperature_max_c` |
| Rain | mm (monthly total, or over a crop cycle; the field says which) | `rainfall_mm`, `rainfall_mm_per_month` |
| Soil moisture | m³/m³ (volume of water per volume of soil) | `moisture_m3m3` |
| Soil wetness | fraction 0–1 (0 dry, 1 saturated) | `wetness_monthly` |
| Root depth | m | `root_depth_m` |
| Cycle | days | `cycle_days` |
| pH | unitless | `soil_ph`, `ph` |
| **Scores** | **0 to 1, 1 = ideal** | `score`, `breakdown`, `variable_scores` |

Numbers are plain JSON numbers with a dot. **Format them for display yourself** (Spanish: `0,98`,
`23,6 °C`). Scores come rounded to 4 decimals: show **at most 2** (or a bar).

### Months, seasons and ids
- Months are integers **1–12, January = 1**. Arrays of 12 are **January first**.
- Seasons are named `primera` (May–Aug) and `postrera` (Sep–Nov) in both languages; the dry season
  (Dec–Apr) is fallow. They come with their `months`.
- Crops are referenced by `id` (`rice`, `beans`, `maize`, `sorghum`, `cowpea`). Use ids in requests,
  names for display.
- Variable ids in `variable_scores` / `limiting_factor`: `temperature`, `rainfall`, `soil_ph`,
  `soil_moisture`, `heat`, `frost` (labels in [§6](#6-label-maps-english--spanish)).

### Where the data comes from: `data_sources`
`/conditions`, `/planting-windows` and `/recommendations` (inside `conditions`) say it:

```json
"data_sources": { "climate": "nasa_power", "soil": "openlandmap+nasa_smap", "crops": "ecocrop_subset" }
```
If you ever see `"mock"`, the server runs on fake data (`data_mode: mock`, only for tests):
show a visible "demo data" banner.

---

## 3. Endpoints

| Method | Path | What it's for | Errors it can return |
|---|---|---|---|
| GET | `/health` | Is the API up? Which mode and region? | 500 |
| GET | `/crops` | The candidate crops with their tolerances and traits | 500 |
| GET | `/conditions?lat&lon` | Climate by month and season + soil at a point | 422, 500, 502, 503 |
| GET | `/planting-windows?lat&lon[&crops]` | Best months to sow each crop | 422, 500, 502, 503 |
| POST | `/recommendations` | Ranked crop rotations, explained, optionally vs the farmer's current one | 422, 500, 502, 503 |

All responses are JSON. All errors share one envelope ([§4](#4-errors)). Every response carries an
`X-Request-ID` header.

---

### GET /health
Use it on app start: check the API is reachable, read the region box (to validate a map pin before
calling) and the data mode.

```json
{ "status": "ok", "version": "0.1.0", "data_mode": "cached",
  "region": { "name": "TBD (placeholder: Costa Rica)", "bbox": [-86.0, 8.0, -82.5, 11.3] } }
```
| Field | Meaning |
|---|---|
| `data_mode` | `cached` (real saved data, demo), `live` (fetches new points) or `mock` (fake: show a banner) |
| `region.bbox` | `[min_lon, min_lat, max_lon, max_lat]`; points outside → `422 out_of_region` |
| `region.name` | still a placeholder: don't show it to farmers yet |

---

### GET /crops
The crops in the MVP scope (today **rice, beans, maize**), with everything known about each. Cache it
for the session; it only changes when the backend data changes.

```json
{ "crops": [ {
  "id": "maize", "name": "Maize", "name_es": "Maíz", "scientific_name": "Zea mays",
  "family": "Poaceae", "is_legume": false, "cycle_days": 120,
  "temperature_c": { "abs_min": 10.0, "opt_min": 18.0, "opt_max": 33.0, "abs_max": 47.0 },
  "rainfall_mm":   { "abs_min": 400.0, "opt_min": 600.0, "opt_max": 1200.0, "abs_max": 1800.0 },
  "soil_ph":       { "abs_min": 4.5, "opt_min": 5.0, "opt_max": 7.0, "abs_max": 8.5 },
  "root_depth_m": 1.7, "is_cover_crop": false, "needs_good_drainage": true,
  "forage_value":         { "level": "medium", "score": 0.67 },
  "nutrition_density":    { "level": "medium", "score": 0.67 },
  "mycorrhizal_affinity": { "level": "high",   "score": 1.0 },
  "nitrogen_demand":      { "level": "high",   "score": 1.0 },
  "market_note": "Staple grain and its fibrous low-protein stover is still valued as cattle feed",
  "sources": [ "FAO EcoCrop ecoportcode 238663 via Adaptation Atlas parquet (tolerance ranges, 2026-11-14)",
               "FAO-56 Table 22 (root depth)", "team estimate (cover crop, nutrition, mycorrhizal, nitrogen demand)",
               "Feedipedia, maize stover (forage: fibrous, low digestibility)" ],
  "verified": true
}, … ] }
```

| Field | Meaning | Show it? |
|---|---|---|
| `name` / `name_es` | Display name EN / ES | Yes |
| `scientific_name`, `family` | Botanical names | Small/secondary (glossary, detail page) |
| `is_legume` | Bean family: takes part of its nitrogen from the air | Badge "Legume / Leguminosa" |
| `cycle_days` | Days from sowing to harvest | Yes ("~120 days") |
| `temperature_c`, `rainfall_mm`, `soil_ph` | **Tolerance ranges** (`ToleranceRange`): outside `abs_min..abs_max` the crop fails; inside `opt_min..opt_max` it's ideal. `rainfall_mm` is **over the whole crop cycle**, not per month | Detail view (range bar, [§5.4](#54-tolerance-ranges)) |
| `root_depth_m` | Typical maximum rooting depth (FAO-56) | Detail view |
| `is_cover_crop` | Commonly grown to cover and protect soil | Badge |
| `needs_good_drainage` | Doesn't tolerate standing water (all but rice). Drives the waterlogging warning | Badge "Needs good drainage / Necesita buen drenaje" |
| `forage_value`, `nutrition_density`, `mycorrhizal_affinity`, `nitrogen_demand` | **Trait levels** (`TraitValue`): `level` word + `score` 0–1. See [§5.2](#52-trait-levels-hover-colours-and-comparison) | Yes: colour chip + hover |
| `market_note` | One line of local market context (**English only**) | Optional |
| `sources` | Where each value comes from | Detail / "Sources" disclosure |
| `verified` | `true` = tolerance ranges come from a cited source (EcoCrop) | Small "verified" tick |

**Trait levels:** `level` is always derived from `score` by the backend (they never disagree):

| `score` | `level` |
|---|---|
| 0 | `none` |
| > 0 and < 0.5 | `low` |
| 0.5 to < 0.8 | `medium` |
| ≥ 0.8 | `high` |

Today the data uses 0, 0.33, 0.67 and 1. Values are team estimates unless `sources` cites them.

---

### GET /conditions
Climate month by month and per season, plus the soil, at one point. Use it for the "your field"
screen (charts) before or alongside the recommendations.

**Request:** `GET /conditions?lat=11.0&lon=-84.6`

```json
{
  "location": { "lat": 11.0, "lon": -84.6 },
  "monthly": [
    { "month": 1, "temperature_c": 24.48, "rainfall_mm": 38.8, "temperature_max_c": 34.07, "temperature_min_c": 17.25 },
    … 12 items, January first …
  ],
  "seasons": [
    { "name": "primera", "months": [5, 6, 7, 8], "temperature_c": 26.17, "rainfall_mm_per_month": 182.7,
      "temperature_max_c": 35.38, "temperature_min_c": 19.68 },
    { "name": "postrera", "months": [9, 10, 11], … }
  ],
  "soil": {
    "ph": 5.4,
    "moisture_m3m3": 0.3032,
    "moisture_monthly_m3m3": [0.319, 0.2857, 0.2426, 0.2139, 0.2079, 0.2636, 0.3255, 0.3551, 0.3542, 0.3573, 0.3644, 0.3486],
    "wetness_monthly":       [0.7579, 0.6787, 0.5764, 0.5083, 0.494, 0.6265, 0.7736, 0.8441, 0.8418, 0.8492, 0.8661, 0.8284],
    "texture_class": "clay"
  },
  "data_sources": { "climate": "nasa_power", "soil": "openlandmap+nasa_smap", "crops": "ecocrop_subset" }
}
```

| Field | Meaning | Source / caveat |
|---|---|---|
| `monthly[].temperature_c` | Mean air temperature, °C | NASA POWER, 2001–2025 averages, ~55 km cell |
| `monthly[].temperature_max_c` / `_min_c` | Mean daily high / low, °C | idem |
| `monthly[].rainfall_mm` | Mean total rain in that month, mm | idem |
| `seasons[]` | Same values summarised per season. `temperature_min_c` = coldest month's mean low (frost) | idem |
| `soil.ph` | Soil pH, 0–30 cm | OpenLandMap map, 250 m (not a soil test) |
| `soil.moisture_monthly_m3m3` | Root-zone (0–100 cm) moisture per month, m³/m³ | NASA SMAP L4 (satellite + model), ~9 km, 2020–2024 |
| `soil.moisture_m3m3` | Yearly mean of the above | idem |
| `soil.wetness_monthly` | How saturated the root zone is, 0–1 (≥ ~0.85 = near saturation) | idem |
| `soil.texture_class` | USDA texture of the topsoil (`clay`, `clay loam`, `sandy loam`, …) | OpenLandMap |

`moisture_monthly_m3m3`, `wetness_monthly` and `texture_class` can be `null` (unknown): hide those
charts instead of drawing zeros.

---

### GET /planting-windows
For each crop: in which months it's good to sow at this point, and why the other months aren't.

**Request:** `GET /planting-windows?lat=11.0&lon=-84.6&crops=maize&crops=beans`
- `crops` is optional and **repeatable** (`&crops=a&crops=b`). Omit it for the MVP crops. Duplicates
  are ignored; order is kept.

```json
{
  "location": { "lat": 11.0, "lon": -84.6 },
  "crops": [ {
    "crop_id": "maize", "crop_name": "Maize", "cycle_days": 120,
    "sowing_months": [
      { "sowing_month": 3, "months_in_field": [3, 4, 5, 6], "score": 0.8603, "is_good": false,
        "limiting_factor": "rainfall",
        "variable_scores": { "temperature": 1.0, "rainfall": 0.3017, "soil_ph": 1.0, "soil_moisture": 1.0, "heat": 1.0, "frost": 1.0 },
        "dry_month_note": {
          "en": "Too dry to establish maize sown in March: March usually gets only 27 mm of rain, and maize needs about 100 mm a month to establish and grow (at least 80)",
          "es": "Muy seco para establecer maíz sembrado en marzo: marzo suele tener solo 27 mm de lluvia, y el maíz necesita unos 100 mm al mes para establecerse y crecer (mínimo 80)" },
        "waterlogging_risk": false },
      … always 12, January first …
    ],
    "fixed_limits": [],
    "windows": [ { "first_month": 5, "last_month": 9, "best_month": 5, "best_score": 1.0 } ]
  }, … ],
  "data_sources": { … }
}
```

| Field | Meaning |
|---|---|
| `sowing_months[]` | Exactly 12, January first: what happens if you sow in that month |
| `months_in_field` | Months the crop is in the field when sown then (cycle rounded up to whole months; wraps the year: sow Nov → `[11, 12, 1, 2]`) |
| `score` | 0–1, same scoring as rotations (includes the small waterlogging penalty) |
| `is_good` | **The one to colour.** `true` = a good month to sow. Already accounts for: score ≥ 0.8 on month-varying factors, no factor below 0.5, and the dry-month check. Don't recompute it from `score` |
| `limiting_factor` | The weakest variable id when it's below 1 (e.g. `rainfall`, `heat`), else `null` = ideal conditions. Label it with [§6](#6-label-maps-english--spanish) |
| `dry_month_note` | Present (else `null`) when the month fails because some month in the field gets too little rain to establish or grow. **Show it as the reason** |
| `waterlogging_risk` | `true` = the soil is usually near saturation during that cycle and the crop needs good drainage. Never makes a month "not good"; show a warning icon |
| `variable_scores` | 0–1 per variable, for a detail tooltip |
| `fixed_limits` | `LocalizedText[]`: things that are the same in every month (today: soil pH) and limit this crop. Show once per crop, above its calendar |
| `windows[]` | Consecutive good months. `first_month`/`last_month` **can wrap** (first 11, last 1 = Nov→Jan). `best_month` = highest score. **Empty list = no good month** |

Real San Carlos results: maize sow **May–Sep** (best May), beans **Jun–Oct** (best Jun); waterlogging
flagged when maize is sown in Aug and beans in Sep.

---

### POST /recommendations
Ranks every crop rotation (one crop per season, repeated every year) for a point, explains each one,
and optionally compares them with the farmer's current rotation.

**Request body:**

| Field | Required | Meaning |
|---|---|---|
| `lat`, `lon` | **yes** | One representative point (never an area average) |
| `crops` | no | Candidate crop ids. Omit → MVP crops. Empty list → 422. Unknown id → `422 unknown_crop` |
| `priorities` | no | `{ "water": n, "soil": n, "climate": n }`, any non-negative numbers; the backend normalises them to sum 1. All 0 → `422 invalid_priorities`. Omit → defaults (water 0.4, soil 0.3, climate 0.3) |
| `top_n` | no | How many rotations to return (1–50). Default 5 |
| `current_rotation` | no | The farmer's rotation: **one crop id per season, in season order** (`["maize", "maize"]` = maize in primera and postrera). Wrong length → `422 invalid_rotation` |

Unknown fields are rejected (`422 validation_failed`): don't send extra keys.

```json
{ "lat": 11.0, "lon": -84.6, "current_rotation": ["maize", "maize"], "top_n": 3,
  "priorities": { "water": 0.4, "soil": 0.3, "climate": 0.3 } }
```

**Response:**

```json
{
  "location": { "lat": 11.0, "lon": -84.6 },
  "region": { "name": "…", "bbox": [ … ] },
  "priorities": { "water": 0.4, "soil": 0.3, "climate": 0.3 },
  "conditions": { … same as GET /conditions … },
  "rotations": [ {
    "rank": 1,
    "sequence": [
      { "season": "primera", "months": [5, 6, 7, 8], "crop_id": "maize", "crop_name": "Maize", "score": 1.0,
        "variable_scores": { "temperature": 1.0, "rainfall": 1.0, "soil_ph": 1.0, "soil_moisture": 1.0, "heat": 1.0, "frost": 1.0 } },
      { "season": "postrera", "months": [9, 10, 11], "crop_id": "beans", "crop_name": "Common bean", "score": 0.9…, … }
    ],
    "score": 0.9842,
    "viable": true,
    "breakdown": { "climate": 0.9817, "water": 1.0, "soil": 0.9667 },
    "explanation": {
      "en": "Maize (primera) → Common bean (postrera): changing crop family cuts pest cycles, the bean-family crop adds a little nitrogen; watch: risk of waterlogging. Score 0.98 of 1.",
      "es": "Maíz (primera) → Frijol (postrera): cambiar de familia corta plagas, la leguminosa aporta un poco de nitrógeno; ojo: riesgo de encharcamiento. Puntaje 0,98 de 1." },
    "is_current": false,
    "score_delta_vs_current": 0.1103,
    "benefits": [ { "en": "Maize after common bean: changing from the bean family to the grass family helps cut pest and disease cycles", "es": "…" }, … ],
    "risks": [ { "en": "Common bean in postrera: strong heat, the average daily high (32.5 °C) is above what the crop tolerates (32 °C)", "es": "Frijol en postrera: calor fuerte, …" }, …,
               { "en": "Local review: check sowing dates and varieties for …", "es": "Revisión local: …" } ],
    "data_gaps": [ { "en": "Soil pH comes from the OpenLandMap soil map (250 m, 0-30 cm), not a soil test of your field", "es": "…" }, … ],
    "evidence": [ { "en": "Soil: pH 5.4 (OpenLandMap soil map, 250 m); root zone saturation in primera (68%) and postrera (85%) (NASA SMAP, ~9 km)", "es": "…" }, … ],
    "notes": [ … deprecated: benefits + risks … ]
  }, … ],
  "current_rotation": { "rank": 3, "score": 0.8738, "is_current": true, "score_delta_vs_current": 0.0, … same shape … },
  "method_version": "suitability-v1",
  "generated_at": "2026-11-15T15:20:47Z"
}
```

| Field | Meaning | How to use it |
|---|---|---|
| `priorities` | The weights actually used, **normalised** to sum 1 | Show next to the sliders ("water 40 %") |
| `conditions` | Same as `GET /conditions` for that point | No need to call `/conditions` again |
| `rotations[]` | Best first (viable before non-viable), at most `top_n` | Cards / list |
| `rank` | Position among **all** combinations (1 = best) | "#1" badge |
| `sequence[]` | One step per season, in order; each with its own `score` and `variable_scores` | Season timeline |
| `score` | 0–1 overall (crop fit + rotation rules) | Main bar |
| `viable` | `false` = at least one crop is outside its absolute limits in its season | Grey out, put last, say "not recommended" |
| `breakdown` | 0–1 per priority category (`climate`, `water`, `soil`); `null` if the category has no variables | Three small bars |
| `explanation` | One sentence: what helps, what to watch, the score | Card headline/subtitle |
| `is_current` | This is the farmer's own rotation | "Your current rotation / Su rotación actual" badge |
| `score_delta_vs_current` | `score − current.score`; `null` without `current_rotation` | "+0.11 vs yours" (green if > 0, red if < 0) |
| `benefits` | Why it helps (never empty) | ✅ list |
| `risks` | What could go wrong; **always ends with 2 "Local review" items** | ⚠️ list; group the "Local review" ones separately (see [§5.5](#55-rotation-cards-and-comparison)) |
| `data_gaps` | What is missing or approximate behind the result (never empty) | "About this data" disclosure: always reachable |
| `evidence` | The data values behind the score, with sources | "See the data" disclosure |
| `notes` | **Deprecated** (= benefits + risks) | Don't use |
| `current_rotation` | The farmer's rotation scored the same way, or `null` | Baseline card. **It can also appear inside `rotations`** when it ranks in the top N: dedupe by `is_current` |
| `method_version` | Scoring method id | Footer / "about" |
| `generated_at` | When the response was built (UTC, ISO 8601) | Footer, staleness |

---

## 4. Errors

Every 4xx/5xx has the same shape. **Switch on `error.code`** (stable); `message` is English and may
change.

```json
{ "error": { "code": "out_of_region",
             "message": "Location (40.0, 0.0) is outside the MVP region 'TBD (placeholder: Costa Rica)'",
             "details": { "lat": 40.0, "lon": 0.0, "bbox": [-86.0, 8.0, -82.5, 11.3] },
             "request_id": "35e75d175dd3" } }
```

| `code` | HTTP | When | What the UI should do | Useful `details` |
|---|---|---|---|---|
| `validation_failed` | 422 | Wrong type, out of range, missing or unknown field, bad JSON | Highlight the field(s) | `fields: [{ loc, message, type }]` (e.g. `loc: "query.lat"`) |
| `out_of_region` | 422 | Point outside the region box | "This location is outside the area we cover (Costa Rica)"; keep the map | `lat`, `lon`, `bbox` |
| `unknown_crop` | 422 | A crop id isn't in the catalog | Re-fetch `/crops`; offer `available` | `unknown`, `available` |
| `invalid_priorities` | 422 | All priority weights are 0 | "Give at least one priority some weight" | `priorities` |
| `invalid_rotation` | 422 | `current_rotation` length ≠ number of seasons | "Pick one crop per season" | `expected_length`, `seasons`, `got` |
| `cache_miss` | **503** | Point not in the saved data (cached mode) | "We don't have data for this exact spot yet. Try a demo point" + buttons for San Carlos / Alajuela. Don't auto-retry | `source` |
| `source_unavailable` | 502 | An external data source failed (live mode) | "Data source temporarily unavailable, try again" + retry | `source` |
| `source_bad_data` | 502 | A source answered unusable data | Same as above; report `request_id` | `source` |
| `not_found` / `method_not_allowed` / `http_error` | 404/405/4xx | Wrong URL or method (a frontend bug) | Generic error; log it | — |
| `internal_error`, `domain_invariant`, `config_invalid` | 500 | Backend bug | Generic "Something went wrong" + show `request_id` so we can find it | hidden |

Real examples: [`docs/errors.md`](errors.md) (full catalog). Always show or log `request_id` (also
in the `X-Request-ID` header) when something fails: it's how we find the log line.

---

## 5. How to display it (UI recommendations)

These are recommendations from the backend team based on what the data means and its limits. Adapt
them to the design system, but keep the **honesty rules** in [§5.9](#59-honesty-rules-dont-skip).

### 5.1 Language
- One switch EN / ES. Every `LocalizedText` → `text[lang]`. Crop names: `name` / `name_es` from
  `/crops` (rotations and windows only give the English `crop_name`: look it up by `crop_id`).
- Format numbers per language: `Intl.NumberFormat(lang === "es" ? "es-CR" : "en-US", { maximumFractionDigits: 2 })`.
- Month names: `Intl.DateTimeFormat(lang === "es" ? "es-CR" : "en-US", { month: "short" })` on
  `new Date(2026, month - 1, 1)`. (Costa Rica writes "setiembre"; the backend's texts already do.)
- Season names `primera` / `postrera` are the same in both languages (local terms). In English, add a
  hint the first time: "primera (first rainy season, May–Aug)".

### 5.2 Trait levels: hover, colours and comparison
The four traits (`forage_value`, `nutrition_density`, `mycorrhizal_affinity`, `nitrogen_demand`)
come as `{ level, score }`. The team asked for three things; here's how the data supports them.

**(1) Hover shows the number.** Show the **word** as a chip; on hover/focus/tap show the score:
> **High** · 1.0 of 1 — *Alta · 1,0 de 1*

Make the tooltip keyboard- and touch-accessible (focusable chip, `aria-describedby`), not hover-only.
Today scores are 0, 0.33, 0.67 or 1 (the bands themselves); finer values will come as sources are added.

**(2) Colour by level, but mind the direction.** For three traits *more is better*; for
`nitrogen_demand` *more means the crop needs more fertilizer* (a cost), so the colours flip:

| Trait | Direction | `none` | `low` | `medium` | `high` |
|---|---|---|---|---|---|
| `forage_value` | more is better | grey | orange | amber | green |
| `nutrition_density` | more is better | grey (not a food crop) | orange | amber | green |
| `mycorrhizal_affinity` | more is better | red-ish (**non-host**: the next crop loses helpful fungi) | orange | amber | green |
| `nitrogen_demand` | **less is better** | green | green | amber | orange |

Suggested accessible palette (text colour on its light background passes WCAG AA contrast):

| Token | Text | Background | Use |
|---|---|---|---|
| good | `#1A7F37` | `#DAFBE1` | green |
| fair | `#9A6700` | `#FFF8C5` | amber |
| poor | `#BC4C00` | `#FFF1E5` | orange |
| warn | `#CF222E` | `#FFEBE9` | red-ish (non-host) |
| neutral | `#57606A` | `#F6F8FA` | grey |

**Never colour alone:** always print the word (and optionally an icon: ▲ high, ■ medium, ▼ low,
○ none). Colour-blind users and printouts must still read it.

**(3) Compare crops side by side.** Use `GET /crops` once and render a table, crops as columns:

| | Maize | Common bean | Rice |
|---|---|---|---|
| Forage value | 🟨 Medium (0.67) | 🟧 Low (0.33) | 🟧 Low (0.33) |
| Nutrition | 🟨 Medium (0.67) | 🟩 High (1.0) | 🟧 Low (0.33) |
| Helpful soil fungi | 🟩 High (1.0) | 🟩 High (1.0) | 🟧 Low (0.33) |
| Nitrogen need | 🟧 High (1.0) | 🟩 Low (0.33) | 🟨 Medium (0.67) |
| Legume | — | ✔ | — |
| Cover crop | — | — | — |
| Needs good drainage | ✔ | ✔ | — (tolerates flooding) |
| Cycle | 120 d | 90 d | 120 d |
| Root depth | 1.7 m | 0.9 m | 1.0 m |

Tips: keep the same row order everywhere; let the user pick which crops to compare (2–4 columns on
mobile, scroll horizontally beyond); a mini horizontal bar (width = score) inside each cell makes
levels scannable; sort rows by "what the farmer chose as priority". On mobile, switch to one card
per trait with the crops inside.

### 5.3 Planting windows: a 12-month calendar per crop
One row per crop, 12 cells (Jan–Dec):
- **Good month** (`is_good: true`): filled green. **Best month** (`windows[].best_month`): star or
  bold border. **Not good**: light grey.
- **Waterlogging** (`waterlogging_risk: true`): small 💧/⚠️ icon in the cell (the month stays green:
  it's a warning, not a no).
- **Tooltip on each cell:**
  - not good + `dry_month_note` → show the note (it explains exactly why);
  - not good, no note → "Limited by: {limiting_factor label}";
  - good + waterlogging → "Risk of waterlogging: check drainage";
  - good, `limiting_factor: null` → "Ideal conditions".
- **On hover/select**, highlight `months_in_field` (the crop's whole stay) to show when it would be
  harvested.
- Windows that **wrap** (`first_month` 11, `last_month` 1) must render across the year boundary.
- `fixed_limits` → one short banner above the crop's row (e.g. soil pH note).
- **Empty `windows`** → write "No good sowing month here" with the reasons from the notes, never an
  empty row without explanation.

### 5.4 Tolerance ranges
For `temperature_c`, `rainfall_mm`, `soil_ph`, draw a horizontal bar: red outside `abs_min..abs_max`,
amber between `abs` and `opt`, green between `opt_min..opt_max`, and a marker for this field's value
(from `/conditions`: season temperature, cycle rain from the rotation's `evidence`, `soil.ph`).
Remember `rainfall_mm` is **per crop cycle**, not per month or year.

### 5.5 Rotation cards and comparison
Card per rotation:
1. **Header:** rank, season timeline `Maíz (primera) → Frijol (postrera)` with crop icons, and the
   score as a bar ("0.98 of 1"; don't show 4 decimals, avoid percent: it reads like a probability).
2. **Delta vs current** when `current_rotation` exists: "+0.11 vs your rotation" (green), "−0.05"
   (red), "same" (grey). The current rotation's own card: badge "Your current rotation".
3. **Subtitle:** `explanation`.
4. **Breakdown:** three small bars climate / water / soil, labelled ([§6](#6-label-maps-english--spanish));
   hide a bar if its value is `null`.
5. **✅ Benefits** (all) and **⚠️ Risks** (rule and season risks). Split out the risks that start
   with "Local review" / "Revisión local" into a separate "Check locally before acting" box; they
   are always the last two and are not problems of this option.
6. **Disclosures:** "About this data" (`data_gaps`), "See the data" (`evidence`).
7. `viable: false` → greyed card, "Not recommended" label, kept at the end.

**Comparing rotations:** side-by-side columns (2–3) with the same rows: score, delta, breakdown bars,
top benefit, top risk, waterlogging yes/no, crops and seasons. Highlight the best value per row.

**Dedupe:** `current_rotation` may also appear in `rotations` (same `rank`, `is_current: true`).

### 5.6 "Your field" charts (from `conditions`)
- **Rain:** 12 bars (`monthly[].rainfall_mm`), seasons shaded behind (primera, postrera), dry months
  pale. Add a 100 mm/month dashed line: a common "wet month" bar for upland crops.
- **Temperature:** line for `temperature_c` with a band between `temperature_min_c` and
  `temperature_max_c`.
- **Soil water:** line for `wetness_monthly` (0–1, label "how saturated the soil is"); shade ≥ 0.85
  as "near saturation". It lags the rain by 1–2 months: say so in a caption, it's a nice insight.
- **Soil badge:** "pH 5.4 · clay" with the source caption "soil map, 250 m".
- Caption under each chart with the source and scale: "NASA POWER, 2001–2025 averages, ~55 km";
  "NASA SMAP, 2020–2024, ~9 km".

### 5.7 Priorities
Three sliders (water, soil, climate). Send raw values; the backend normalises them. Show the
normalised `priorities` from the response ("Water 40 % · Soil 30 % · Climate 30 %"). Block the
"all zero" state in the UI (it's a 422 otherwise). Re-request on change (debounce ~300 ms).

### 5.8 Loading and caching
- In `cached` mode answers are fast (local files). Still show skeletons for charts and cards.
- Cache `/crops` and `/health` for the session. Cache `/conditions`, `/planting-windows` and
  `/recommendations` per `(lat, lon rounded to 2 decimals, crops, priorities, current_rotation)`.
- `generated_at` changes on each call even when the result doesn't: don't use it as a cache key.
- Never call the backend in a loop over map hover; call on pin drop / confirm.

### 5.9 Honesty rules (don't skip)
- Always offer `data_gaps` (one tap away), and source captions under charts. Judges will ask.
- Don't present scores as yield, profit or probability. "Suitability 0.98 of 1" is fine;
  "98 % chance of success" is not.
- Satellite and map data describe an area (~9 km SMAP, ~55 km POWER, 250 m soil map), not the
  farmer's exact field: keep the "not measured in your field" wording the backend gives.
- If `data_sources` contains `mock`, show a "demo data" banner.
- Waterlogging and dry-month notes are **warnings to check locally**, not verdicts.

### 5.10 Accessibility and mobile
Target WCAG 2.2 AA (as in the frontend proposal): colour + text, focusable tooltips, 360 px wide
layouts (calendar cells can shrink to initials "E F M A M J J A S O N D"), tables become cards.

---

## 6. Label maps (English / Spanish)

Copy these into the frontend (the backend sends ids for these):

```ts
export const VARIABLE_LABELS = {
  temperature:   { en: "Average temperature",       es: "Temperatura promedio" },
  rainfall:      { en: "Rain over the crop cycle",  es: "Lluvia durante el ciclo" },
  soil_ph:       { en: "Soil pH",                   es: "pH del suelo" },
  soil_moisture: { en: "Soil moisture (dry soil)",  es: "Humedad del suelo (suelo seco)" },
  heat:          { en: "Heat (daily highs)",        es: "Calor (máximas diarias)" },
  frost:         { en: "Frost (coldest nights)",    es: "Helada (noches más frías)" },
} as const;

export const CATEGORY_LABELS = {
  climate: { en: "Climate", es: "Clima" },
  water:   { en: "Water",   es: "Agua" },
  soil:    { en: "Soil",    es: "Suelo" },
} as const;

// Trait names and their level words. Spanish adjectives agree with the noun's gender.
export const TRAITS = {
  forage_value:         { en: "Forage value",       es: "Valor forrajero",          direction: "higher_is_better", esGender: "m" },
  nutrition_density:    { en: "Nutrition",          es: "Densidad nutricional",     direction: "higher_is_better", esGender: "f" },
  mycorrhizal_affinity: { en: "Helpful soil fungi", es: "Afinidad con micorrizas",  direction: "higher_is_better", esGender: "f" },
  nitrogen_demand:      { en: "Nitrogen need",      es: "Demanda de nitrógeno",     direction: "lower_is_better",  esGender: "f" },
} as const;

export const LEVEL_WORDS = {
  en: { none: "None", low: "Low", medium: "Medium", high: "High" },
  es: {
    m: { none: "Nulo", low: "Bajo", medium: "Medio", high: "Alto" },
    f: { none: "Nula", low: "Baja", medium: "Media", high: "Alta" },
  },
} as const;
// Special case: mycorrhizal_affinity "none" means the crop doesn't host the fungi:
// show "Non-host" / "No hospedero" instead of "None".

export const SEASON_HINTS = {
  primera:  { en: "first rainy season (May–Aug)",  es: "primera (mayo–agosto)" },
  postrera: { en: "second rainy season (Sep–Nov)", es: "postrera (setiembre–noviembre)" },
} as const;

export const BADGES = {
  is_legume:           { en: "Legume",              es: "Leguminosa" },
  is_cover_crop:       { en: "Cover crop",          es: "Cultivo de cobertura" },
  needs_good_drainage: { en: "Needs good drainage", es: "Necesita buen drenaje" },
  verified:            { en: "Ranges from source",  es: "Rangos con fuente" },
} as const;
```

---

## 7. TypeScript types

Hand-written from the contract (or generate them: `npx openapi-typescript http://localhost:8000/openapi.json -o api.d.ts`).

```ts
export type Lang = "en" | "es";
export interface LocalizedText { en: string; es: string }
export type Level = "none" | "low" | "medium" | "high";
export interface TraitValue { level: Level; score: number }            // score 0..1
export interface ToleranceRange { abs_min: number; opt_min: number; opt_max: number; abs_max: number }
export interface Region { name: string; bbox: [number, number, number, number] }
export interface Location { lat: number; lon: number }
export interface DataSources { climate: string; soil: string; crops: string }

export interface HealthResponse { status: string; version: string; data_mode: "cached" | "live" | "mock"; region: Region }

export interface Crop {
  id: string; name: string; name_es: string; scientific_name: string; family: string;
  is_legume: boolean; cycle_days: number;
  temperature_c: ToleranceRange; rainfall_mm: ToleranceRange; soil_ph: ToleranceRange;
  root_depth_m: number; is_cover_crop: boolean; needs_good_drainage: boolean;
  forage_value: TraitValue; nutrition_density: TraitValue;
  mycorrhizal_affinity: TraitValue; nitrogen_demand: TraitValue;
  market_note: string; sources: string[]; verified: boolean;
}
export interface CropsResponse { crops: Crop[] }

export interface MonthClimate { month: number; temperature_c: number; rainfall_mm: number; temperature_max_c: number; temperature_min_c: number }
export interface SeasonSummary { name: string; months: number[]; temperature_c: number; rainfall_mm_per_month: number; temperature_max_c: number; temperature_min_c: number }
export interface Soil {
  ph: number; moisture_m3m3: number;
  moisture_monthly_m3m3: number[] | null; wetness_monthly: number[] | null; texture_class: string | null;
}
export interface Conditions { location: Location; monthly: MonthClimate[]; seasons: SeasonSummary[]; soil: Soil; data_sources: DataSources }

export type VariableId = "temperature" | "rainfall" | "soil_ph" | "soil_moisture" | "heat" | "frost";
export interface SowingMonth {
  sowing_month: number; months_in_field: number[]; score: number; is_good: boolean;
  dry_month_note: LocalizedText | null; waterlogging_risk: boolean;
  limiting_factor: VariableId | null; variable_scores: Partial<Record<VariableId, number>>;
}
export interface PlantingWindow { first_month: number; last_month: number; best_month: number; best_score: number }
export interface CropPlanting {
  crop_id: string; crop_name: string; cycle_days: number;
  sowing_months: SowingMonth[]; fixed_limits: LocalizedText[]; windows: PlantingWindow[];
}
export interface PlantingWindowsResponse { location: Location; crops: CropPlanting[]; data_sources: DataSources }

export interface Priorities { water: number; soil: number; climate: number }
export interface RecommendationRequest {
  lat: number; lon: number; crops?: string[]; priorities?: Priorities; top_n?: number; current_rotation?: string[];
}
export interface RotationStep { season: string; months: number[]; crop_id: string; crop_name: string; score: number; variable_scores: Partial<Record<VariableId, number>> }
export interface CategoryBreakdown { climate: number | null; water: number | null; soil: number | null }
export interface Rotation {
  rank: number; sequence: RotationStep[]; score: number; viable: boolean; breakdown: CategoryBreakdown;
  explanation: LocalizedText; is_current: boolean; score_delta_vs_current: number | null;
  benefits: LocalizedText[]; risks: LocalizedText[]; data_gaps: LocalizedText[]; evidence: LocalizedText[];
  /** @deprecated benefits + risks */ notes: LocalizedText[];
}
export interface RecommendationResponse {
  location: Location; region: Region; priorities: Priorities; conditions: Conditions;
  rotations: Rotation[]; current_rotation: Rotation | null; method_version: string; generated_at: string;
}

export type ErrorCode =
  | "validation_failed" | "out_of_region" | "unknown_crop" | "invalid_priorities" | "invalid_rotation"
  | "not_found" | "method_not_allowed" | "http_error" | "source_unavailable" | "source_bad_data"
  | "cache_miss" | "config_invalid" | "domain_invariant" | "internal_error";
export interface ErrorResponse { error: { code: ErrorCode; message: string; details: Record<string, unknown>; request_id: string } }
```

A tiny fetch helper:

```ts
const API = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  const body = await res.json();
  if (!res.ok) throw body as ErrorResponse;          // switch on body.error.code
  return body as T;
}

// Repeated query params for crops:
const q = new URLSearchParams({ lat: "11.0", lon: "-84.6" });
["maize", "beans"].forEach((c) => q.append("crops", c));
const windows = await api<PlantingWindowsResponse>(`/planting-windows?${q}`);
```

---

## 8. Known gaps and gotchas

Things the backend doesn't do yet, so you don't build on wrong assumptions (tracked for the backend):

| Gap | Effect on the frontend | Workaround today |
|---|---|---|
| Only 2 points have data (`cached`) | Any other pin → `503 cache_miss` | Offer the demo points; design the map around San Carlos |
| `GET /crops` lists only the MVP crops (rice, beans, maize), but requests also accept `sorghum` and `cowpea` | Spanish names and traits of those two aren't fetchable | Stick to the MVP crops in the UI for now |
| `crop_name` in rotations / windows is English only | Need Spanish names there | Look up `name_es` in `/crops` by `crop_id` |
| `Crop.market_note` is English only | — | Show only in English, or hide in Spanish |
| Error `message` is English only | — | Map `error.code` to your own text |
| "Local review" items live inside `risks` | They inflate the risk count | Split by prefix ("Local review" / "Revisión local"); they're always the last two |
| `region.name` is a placeholder ("TBD …") | — | Don't show it; say "Costa Rica" |
| Seasons are fixed (primera May–Aug, postrera Sep–Nov), not the local calendar | Late (Nov–Jan) bean sowings don't appear | Show the "Local review" note; planting windows give the month-by-month view |
| Trait scores are bands (0, 0.33, 0.67, 1) | The hover number adds little yet | Still show it; finer values come with sourced data |
| No endpoint for terrain/erosion, daily weather indicators or the full soil profile (they exist inside the backend) | — | Ask if a screen needs them: it's a contract addition |
| No accounts, saving or area (polygon) input | Everything is per request, per point | Keep state in the frontend |

**Gotchas:**
- `rainfall_mm` in crops is **per crop cycle**; `monthly[].rainfall_mm` is **per month**.
- `score_delta_vs_current` is `null` without `current_rotation` (not 0).
- `current_rotation` may be duplicated inside `rotations` (dedupe by `is_current`).
- `top_n` limits the list; the current rotation is always returned separately, even if it ranks lower.
- Planting `windows` can wrap the year; `sowing_months` is always 12 items, January first.
- `is_good` already includes the dry-month check: don't recompute "good" from `score`.
- Arrays like `moisture_monthly_m3m3` / `wetness_monthly` can be `null`.
- `generated_at` changes every call.

---

## 9. Where things live

| What | Where |
|---|---|
| API contract (source of truth for shapes) | [`backend/docs/api-contract.yaml`](api-contract.yaml) |
| Real example responses (CI-checked) | [`backend/docs/examples/`](examples/README.md) |
| Bruno / Postman requests | [`backend/docs/bruno/`](bruno/README.md) |
| Error catalog | [`backend/docs/errors.md`](errors.md) |
| Why things work the way they do | [`backend/docs/decisions.md`](decisions.md) |
| Data sources (units, resolution, licenses) | [`backend/docs/sources/`](sources/) |
| Crop fields and traits | [`backend/docs/crop-schema.md`](crop-schema.md) |
| Frontend design proposal (screens, journey) | [`docs/frontend-requirements-proposal.md`](../../docs/frontend-requirements-proposal.md) |

Questions or a field you need that isn't here: open an issue tagged `frontend` or ask the backend
team. API changes are contract-first: we agree the shape, update `api-contract.yaml`, then build.
