# NASA POWER: Climatology and Daily APIs

| Field | Value |
|---|---|
| **Used for** | Temperature and rainfall (`ClimateSource`) |
| **Adapter** | `app/integrations/nasa_power.py` |
| **Fixtures** | `tests/fixtures/nasa_power/climatology_alajuela.json` (lat 10.0, lon −84.2, fetched 2026-11-06)<br>`tests/fixtures/nasa_power/daily_san_jose_202601.json` (lat 9.93, lon −84.08, 2026-01-01 to 2026-01-31, fetched 2026-11-14) |
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
- Request: `parameters=T2M,PRECTOTCORR`, `community=AG`, `start` / `end` as `YYYYMMDD` (inclusive).
- Response shape: `properties.parameter.<PARAM>.{YYYYMMDD: value}`, `header.time_standard` = LST (local solar time).
- Returned as a pandas DataFrame: `date`, `temperature_c` (T2M daily mean, °C), `rainfall_mm`
  (PRECTOTCORR, **mm/day = that day's total**, no conversion).
- Fill values (−999) become NaN per day instead of failing the whole request; only an all-missing
  series raises `source_bad_data`. Callers must handle NaN (e.g. `skipna` in pandas aggregations).
- Recent days may be missing: MERRA-2 data arrives with a lag of a few weeks.
- Cache namespace `nasa_power_daily`, keyed by lat/lon (2 decimals) and start/end.
- Not wired into `services.py` or the `ClimateSource` protocol yet; it is the base for dry-spell,
  heat-wave and frost-day calculations.

## Next steps
- `T2M_MAX`/`T2M_MIN` now feed `heat` and `frost`. Next: the daily endpoint for extremes (dry spells, heat waves, frost-day counts).
- Consider the `climatology` vs. recent-years trend to show climate shift (the "Field Shift" angle).
