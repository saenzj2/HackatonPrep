# NASA POWER: Climatology API

| Field | Value |
|---|---|
| **Used for** | Temperature and rainfall (`ClimateSource`) |
| **Adapter** | `app/integrations/nasa_power.py` |
| **Fixture** | `tests/fixtures/nasa_power/climatology_alajuela.json` (lat 10.0, lon −84.2, fetched 2026-11-06) |
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
| `T2M_MAX` | Mean daily max temperature at 2 m | °C | not used yet (heat stress) |
| `T2M_MIN` | Mean daily min temperature at 2 m | °C | not used yet (cold stress) |
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

## Next steps
- Use `T2M_MAX`/`T2M_MIN` for heat and cold stress, or the daily endpoint for extremes (dry spells, heat waves).
- Consider the `climatology` vs. recent-years trend to show climate shift (the "Field Shift" angle).
