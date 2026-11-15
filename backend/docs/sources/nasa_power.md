# NASA POWER: Climatology and Daily APIs

| Field | Value |
|---|---|
| **Used for** | Temperature and rainfall (`ClimateSource`) |
| **Adapter** | `app/integrations/nasa_power.py` |
| **Fixtures** | `tests/fixtures/nasa_power/climatology_alajuela.json` (lat 10.0, lon −84.2, fetched 2026-11-06)<br>`tests/fixtures/nasa_power/daily_san_jose_202601.json` (lat 9.93, lon −84.08, 2026-01-01 to 2026-01-31, `T2M,T2M_MAX,T2M_MIN,PRECTOTCORR`, refetched 2026-11-14)<br>`tests/fixtures/nasa_power/daily_history_san_carlos_202009_202011.json` (lat 11.0, lon −84.6, 2020-09-01 to 2020-11-30, `IMERG_PRECTOT,PRECTOTCORR,T2M_MAX,T2M_MIN,GWETROOT`, UTC, fetched 2026-11-15) |
| **Status** | ✅ Integrated (`live` / `cached` modes) |

## Access
- Endpoint: `GET https://power.larc.nasa.gov/api/temporal/climatology/point`
- Auth: **none** (no key). Be polite: the cache avoids repeating requests.
- Docs: https://power.larc.nasa.gov/docs/services/api/temporal/climatology/
- License: NASA open data, free to use. Cite "NASA POWER Project".

Example:
```
https://power.larc.nasa.gov/api/temporal/climatology/point?parameters=T2M,T2M_MAX,T2M_MIN,PRECTOTCORR&community=AG&longitude=-84.2&latitude=10.0&format=JSON
```

## Variables we request

| Parameter | Meaning | Native unit | We convert to |
|---|---|---|---|
| `T2M` | Mean air temperature at 2 m | °C | °C (as is) |
| `T2M_MAX` | Mean daily max temperature at 2 m | °C | `heat` variable: season mean vs crop abs max |
| `T2M_MIN` | Mean daily min temperature at 2 m | °C | `frost` variable: coldest month in the season |
| `PRECTOTCORR` | Bias-corrected precipitation | **mm/day** | **mm/month** (× days in month, Feb = 28.25) |

Response shape: `properties.parameter.<PARAM>.{JAN..DEC, ANN}`. Missing data = `header.fill_value` (−999).

## Coverage and resolution
- Global. Period: **January 2001 to December 2025** (25-year climatology, per `header.range`).
- Sources: MERRA-2 (meteorology). Native grid is about 0.5° × 0.625° (~55 km × 70 km at Costa Rica's latitude),
  so nearby farms share values. The response also returns grid elevation (`geometry.coordinates[2]`, 657 m for the fixture).
- Costa Rica: covered. Coarse resolution smooths the strong elevation gradients (e.g. Central Valley vs.
  coast). Worth comparing a few points against IMN station data if time allows.

## Sample values (fixture, lat 10.0 lon −84.2)
- T2M: 22.5 °C (Dec) to 25.2 °C (Apr), annual 23.45 °C
- PRECTOTCORR: 0.79 mm/day (Feb) to 9.71 mm/day (Oct), so roughly 22 to 301 mm/month. Clear dry season Dec to Apr.

## Gotchas
- Precipitation is a **daily rate**; multiply by the days in the month.
- The `ANN` key appears next to the months. Ignore it when building the 12-month series.
- Latitude/longitude are rounded to 2 decimals for the cache key.

## Daily API (`NasaPowerClimate.daily_weather`)
- Endpoint: `GET https://power.larc.nasa.gov/api/temporal/daily/point`, same auth (none) and license.
- Docs: https://power.larc.nasa.gov/docs/services/api/temporal/daily/
- Request: `parameters=T2M,T2M_MAX,T2M_MIN,PRECTOTCORR`, `community=AG`, `start` / `end` as `YYYYMMDD` (inclusive).
- Daily variables (units as declared in the response's `parameters.<P>.units`):

  | Parameter | Meaning | Unit | Column |
  |---|---|---|---|
  | `T2M` | Daily **mean** air temperature at 2 m | `C` | `temperature_c` |
  | `T2M_MAX` | That day's **maximum** air temperature at 2 m | `C` | `temperature_max_c` |
  | `T2M_MIN` | That day's **minimum** air temperature at 2 m | `C` | `temperature_min_c` |
  | `PRECTOTCORR` | Bias-corrected precipitation | `mm/day` | `rainfall_mm` (the day's total) |

  A response declaring other units is rejected (`source_bad_data`); nothing is converted.
- Response shape: `properties.parameter.<PARAM>.{YYYYMMDD: value}`, `header.time_standard` = LST (local solar time).
- Returned as a pandas DataFrame: `date`, `temperature_c`, `temperature_max_c`, `temperature_min_c`,
  `rainfall_mm` (see the table above). Fixture sanity check: max ≥ mean ≥ min on every day.
- Fill values (−999) become NaN per day instead of failing the whole request; only an all-missing
  series raises `source_bad_data`. Callers must handle NaN (e.g. `skipna` in pandas aggregations).
- Recent days may be missing: MERRA-2 data arrives with a lag of a few weeks.
- Cache namespace `nasa_power_daily`, keyed by the full query (parameters, lat/lon to 2 decimals,
  start/end). Entries cached before `T2M_MAX` / `T2M_MIN` were added sit under a different key and
  are not served; refetch once in `live` mode.
- Used by `services.erosion_risk()` and `services.field_indicators()` (monthly indicators,
  `docs/indicators.md`). Heat-stress and frost days use `T2M_MAX` / `T2M_MIN`, never the mean `T2M`.

## Daily history (`NasaPowerClimate.daily_history`, for `POST /plan-risk`)
Every past year of daily weather at one point, to replay a planting against it.
- Same endpoint as the daily API, but its own parameters, params builder
  (`history_request_params`) and cache namespace **`nasa_power_daily_history`**, so it never changes
  `daily_weather`'s cache keys.
- Request: `parameters=IMERG_PRECTOT,PRECTOTCORR,T2M_MAX,T2M_MIN,GWETROOT`, `community=AG`,
  **`time-standard=UTC`**, `start`/`end` `YYYYMMDD`.

  | Parameter | Meaning | Grid | Unit (declared) | Column |
  |---|---|---|---|---|
  | `IMERG_PRECTOT` | GPM IMERG satellite precipitation. **The rain the engine uses** | ~0.1° (~10 km) | `mm/day` | `rainfall_mm` |
  | `PRECTOTCORR` | MERRA-2 bias-corrected precipitation. Only to report the gap vs IMERG | ~0.5° × 0.625° | `mm/day` | `rainfall_merra2_mm` |
  | `T2M_MAX` / `T2M_MIN` | Daily max / min air temperature at 2 m | ~0.5° × 0.625° | `C` | `temperature_max_c` / `temperature_min_c` |
  | `GWETROOT` | Root-zone soil wetness (MERRA-2 land model), 0 dry .. 1 saturated | ~0.5° × 0.625° | `1` (dimensionless fraction) | `root_wetness` |

- **Verified live on 2026-11-15** (Los Chiles, lat 11.0, lon −84.6, API v2.10.3):
  - **`time-standard=UTC` is required for IMERG.** With the default (LST) the API answers 200 but
    every `IMERG_PRECTOT` value is the −999 fill, and `header.sources` omits IMERG. With UTC the
    header lists `MERRA2, IMERG, POWER`. Consequence: days are **UTC days** (18:00–18:00 in
    Costa Rica, UTC−6). Fine for multi-day windows (establishment, flowering, harvest); don't read
    single-day rain as a calendar day.
  - **First IMERG day: 2000-06-01.** No fill values inside 2000-06-01 → 2026-09-14.
  - **Latency:** on 2026-11-15 the last IMERG day was **2026-09-14** (~2 months); MERRA-2 variables
    reached 2026-10-31. The 47 days after Sep 14 were −999 for IMERG only.
  - **Fill value:** −999 (`header.fill_value`). Becomes NaN per variable; a variable with no data
    at all is rejected (`source_bad_data`) and never cached.
  - **Size:** the whole range 2000-06-01 → 2026-10-31 in one request: 9,649 days, 0.8 MB, ~2 s.
- **IMERG vs MERRA-2 at Los Chiles (annual totals, mm):** IMERG is higher in 24 of the 26 years
  2000–2025 (2000 from June), by 14–126 % (e.g. 2001: 2,401 vs 1,128; 2015: 1,927 vs 1,062). MERRA-2 is higher only in
  **2020 (2,682 vs 3,064)** and **2024 (2,723 vs 3,603)**, driven by single extreme days: on
  **2020-11-03 (hurricane Eta) MERRA-2 has 513 mm and IMERG 4 mm**; November 2020 totals are 1,010
  mm (MERRA-2) vs 328 mm (IMERG). The two sources disagree on Eta/Iota at this point; which one is
  closer to local gauges is **unverified** (task for the `fact-checker` / IMN station data).
- **Fixture:** `tests/fixtures/nasa_power/daily_history_san_carlos_202009_202011.json`, the real
  response for lat 11.0, lon −84.6, 2020-09-01 → 2020-11-30, UTC, fetched 2026-11-15 (includes Eta).
- Tests: `tests/test_daily_history.py` (parse, units, fills, live → cached, fallback, miss, network).

## Next steps
- `T2M_MAX`/`T2M_MIN` now feed `heat` and `frost`. Daily dry spells and extreme-rain days are done (`docs/indicators.md`). Daily `T2M_MAX` / `T2M_MIN` feed heat-stress and frost-day counts.
- Consider the `climatology` vs. recent-years trend to show climate shift (the "Field Shift" angle).
