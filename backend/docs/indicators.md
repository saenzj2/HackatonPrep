# Field indicators (monthly, from daily data)

Code: `app/domain/indicators.py` (`monthly_indicators`), `app/services.py` (`field_indicators`).
Tests: `tests/test_indicators.py`. Not exposed over HTTP yet (that needs an `api-contract.yaml` change, see #40).

`field_indicators(weather_source=..., lat=..., lon=..., start=..., end=...)` reads the daily series
from a `DailyWeatherSource` (NASA POWER daily in `live` / `cached` mode, `MockClimate` in `mock`)
and returns one row per calendar month in `start..end`.

## Indicators and thresholds

| Field | Unit | Rule | Threshold source |
|---|---|---|---|
| `mean_temperature_c` | °C | mean of the daily mean temperatures (POWER `T2M`) | — |
| `total_rainfall_mm` | mm per month (or partial month) | sum of daily totals (POWER `PRECTOTCORR`, mm/day) | — |
| `dry_days` | days | rainfall `< 1 mm` | `DRY_DAY_MM = 1.0`, ETCCDI wet-day threshold (CDD, R1mm) |
| `longest_dry_spell_days` | days | longest run of consecutive dry days inside the month | same as above |
| `extreme_rain_days` | days | rainfall `>= 30 mm` | `EXTREME_RAIN_MM` = erosion's `HEAVY_RAIN_MM` (placeholder) |
| `heat_stress_days` | days | daily **max** `>= 35 °C` | `HEAT_STRESS_MAX_C = 35.0`, placeholder (see below) |
| `frost_days` | days | daily **min** `<= 0 °C` | `FROST_MIN_C` = suitability's `FROST_C` (air frost) |

## Heat-stress and frost days need true daily extrema

NASA POWER daily `T2M` is the **daily mean**. A mean cannot tell whether the afternoon passed 35 °C
or the dawn reached 0 °C, so `heat_stress_days` and `frost_days` are **`None`** whenever the source
gives only the mean. They are never estimated from the mean or from monthly normals.

They are computed only when the daily series also has `temperature_max_c` and `temperature_min_c`
columns (true daily max / min). The NASA POWER daily adapter requests `T2M_MAX` / `T2M_MIN` (°C,
that day's max / min of 2 m air temperature) alongside `T2M`, so both counts are real for POWER data.
The mock source has no extrema, so in `mock` mode both stay `None`.

Cache: adding the two parameters changed the daily cache key. Entries cached before that are never
served (they have no extrema); refetch the point once in `live` mode (`docs/decisions.md`).

Known limits:
- 35 °C is a **provisional** generic heat level often cited for flowering damage in maize and
  beans; it is not crop-specific and has not had an `agro-logic` review. Do not score it before that
  review.
- POWER temperatures are 2 m air on a ~50 km grid. Ground frost can happen with a 2 m minimum a few
  degrees above 0 °C, and valley bottoms are colder than the grid cell, so frost days are undercounted.

## Missing days

POWER fill values (−999) become NaN in `parse_daily`. In the indicators:
- Each indicator only uses the days with data for its variable. `temperature_days`, `rainfall_days`
  and `extrema_days` say how many that was; `days` is how many days of the month are in `start..end`.
- `total_rainfall_mm` is the sum over `rainfall_days` only, so a month with gaps is an **undercount**.
  Compare `rainfall_days` with `days` before trusting it.
- A missing day **ends** a dry spell (we cannot call it dry).
- A month with no data for a variable gives `None`, never `0`.
- `extrema_days` counts days with both max and min present. A day missing either one is left out of
  both heat-stress and frost counts (never filled from the mean).

Other rules: months are calendar months, so a partial first or last month is reported as is (check
`days`), and a dry spell crossing a month boundary is counted in each month separately.

## Indicator table: fixture point

Demo fields are not chosen yet (#15). Until then, this is the table for the only daily fixture,
`tests/fixtures/nasa_power/daily_san_jose_202601.json` (lat 9.93, lon −84.08, Jan 2026). It is
asserted in `test_field_indicators_on_the_power_fixture`.

| Month | Days (temp / rain / extrema) | Mean temp (°C) | Rain (mm) | Dry days | Longest dry spell | Extreme-rain days | Heat-stress days | Frost days |
|---|---|---|---|---|---|---|---|---|
| 2026-01 | 31 (31 / 31 / 31) | 22.44 | 35.2 | 20 | 11 (Jan 19–29) | 0 | 0 (max 28.03 °C) | 0 (min 17.33 °C) |

To produce the table for a demo field once it is chosen, call `field_indicators` with that field's
lat/lon and period in `cached` mode after the daily response has been cached.

## Open gaps (issue #19 stays open)

- **Unvalidated heat threshold.** `HEAT_STRESS_MAX_C = 35.0` is a generic placeholder with no
  `agro-logic` review and no crop-specific values. Nothing scores it yet.
- **No demo-field tables.** Demo fields are not chosen (#15) and their daily responses are not
  cached (#18). The table above is for the test fixture point only, not a demo field.
