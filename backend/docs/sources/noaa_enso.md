# NOAA CPC El Niño indices: RONI (official) and ONI (legacy)

| Field | Value |
|---|---|
| **Used for** | El Niño / La Niña label of each sowing year and the current phase in `POST /plan-risk` (`enso_now`, `years[].enso`, `enso_split`) |
| **Adapter** | `app/integrations/noaa_enso.py` (`NoaaEnso.index("RONI" \| "ONI")`, `parse_enso_index`); domain logic in `app/domain/enso.py` |
| **Fixtures** | `tests/fixtures/noaa_enso/RONI_ascii_2026-11-15.txt` and `oni_ascii_2026-11-15.txt`: the **full** files (15 KB, 23 KB), fetched 2026-11-15, `Last-Modified: Tue, 03 Nov 2026 19:31:48 GMT`, last season ASO 2026 |
| **Status** | ✅ Integrated (`live` / `cached`; deterministic `MockEnso` in `mock`). Tests: `tests/test_noaa_enso.py` |

## Which index (decided 2026-11-15, see `decisions.md`)
- **RONI (Relative Oceanic Niño Index) is NOAA CPC's official index** for ENSO monitoring,
  prediction and El Niño / La Niña classification **since 2026-02-01** (NWS Public Information
  Statement 26-05, 2026-01-13). The legacy ONI file "will continue to be updated for users that
  require that continuity".
- Why NOAA switched (same statement): the relative index "is less sensitive to the chosen base
  climatology period", so events compare across the whole record, and it "was better aligned with
  the intensity of rainfall anomalies and circulation changes" tied to ENSO. Our 2000–2025
  comparison spans several ONI base periods, and plan-risk is about rain.
- No study found comparing RONI and ONI for Central American or Costa Rican rainfall (searched
  2026-11-15). So the response says how many years the legacy ONI would label differently.

## Access
- RONI: `GET https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt`
- ONI: `GET https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt`
- Auth: none. Plain text (`text/plain; charset=utf-8`), one row per 3-month season.
- Docs: https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/ ,
  https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/ ,
  NWS PNS 26-05: https://www.weather.gov/media/notification/pdf_2026/pns26-05_Relative_ONI.pdf
- License / citation: NOAA Climate Prediction Center, a US government work (public domain;
  NWS disclaimer https://www.weather.gov/disclaimer.php). Cite "NOAA CPC Relative Oceanic Niño
  Index (RONI), ERSST v6".

Example request:
```
curl https://www.cpc.ncep.noaa.gov/data/indices/RONI.ascii.txt
```

## Variables
| File | Columns | Meaning | Native unit | Convert to |
|---|---|---|---|---|
| RONI | `SEAS YR ANOM` | 3-month running mean of the relative Niño 3.4 index: ERSST v6 SST anomaly in Niño 3.4 (5°N–5°S, 120°–170°W) minus the tropical-mean (20°N–20°S) anomaly, rescaled to the variance of the traditional index; 1991–2020 base | °C anomaly | none (`oni_c` / anomaly °C) |
| ONI | `SEAS YR TOTAL ANOM` | 3-month running mean of the ERSST v6 Niño 3.4 SST anomaly, centered 30-year base periods updated every 5 years; `TOTAL` is the SST itself | °C anomaly (`ANOM`) | none |

`SEAS` is the 3-month season named by its initials: `DJF` (Dec–Feb, centred on January) … `NDJ`
(Nov–Jan, centred on December). The season **centred on month m** is the m-th in
`DJF, JFM, FMA, MAM, AMJ, MJJ, JJA, JAS, ASO, SON, OND, NDJ`. `YR` is the year of the middle month
(`NDJ 2025` = Nov 2025–Jan 2026, `DJF 2025` = Dec 2024–Feb 2025).

## Coverage and resolution
- Spatial: one global index (tropical Pacific). No point, so no lat/lon in the request.
- Temporal: DJF 1950 → latest season, monthly update "by the 5th of each month"; the file is
  rewritten whole. **The last ~2 values are estimates**: "RONI values may change up to two months
  after the initial 'real time' value is posted" (high-frequency filter of ERSST v6).
- Pilot region: n/a (global index). ENSO's effect on rain differs inside Costa Rica: Los Chiles
  (Zona Norte) is a transition zone between the Caribbean and Pacific regimes, so plan-risk reports
  what the point's own history shows, never "El Niño = drought".

## Sample values (fixtures, checked 2026-11-15)
- RONI: 921 rows, DJF 1950 → ASO 2026; every full year has 12 seasons in order; 2026 has 9.
  ASO 2026 = **+1.97** (El Niño). 2015 NDJ +2.3, 2020 OND −1.5, 2024 OND −0.9.
- ONI: 921 rows, same span. ASO 2026 = +2.46. ONI runs higher than RONI in recent years (warming
  tropics), e.g. 2020 DJF ONI +0.71 vs RONI +0.1.
- **Labels by sowing year 2000–2025 (±0.5 °C on the season centred on the sowing month)** differ
  between the two in 3–5 of 26 years: May (AMJ) 5 years (2010, 2016, 2019, 2020, 2021), Sep (ASO) 5
  (2016, 2017, 2018, 2024, 2025), Nov/Dec 3 (2016, 2019, 2024).

## Gotchas
- Not JSON: the cache stores the text inside a JSON object. Parse by whitespace; RONI has 3
  columns, ONI 4 (take the last as the anomaly).
- The header row is `SEAS YR ANOM` / ` SEAS  YR   TOTAL   ANOM` (leading spaces in ONI).
- Recent values are revised: never hardcode them. The cache key is just `{"index": "RONI"}`: in
  `live` mode a copy fetched less than `MAX_AGE` (1 day) ago is reused, after that `JsonCache`
  refetches (falling back to the last good copy), so new months arrive without a dated key;
  `cached` mode serves the last saved copy whatever its age (a dated key would make the
  committed snapshot miss every new month).
- NOAA's **episode** definition needs ±0.5 °C for ≥ 5 consecutive overlapping seasons. Plan-risk
  labels a **sowing year** by the single season centred on the sowing month (a placeholder rule,
  decisions.md), which is simpler and not the same as NOAA's episode list.
- `oni.ascii.txt` values now match NOAA's ONI v6 (ERSST v6) table, not v5.

## Verdict and next steps
**Use RONI** for `years[].enso`, `enso_split` and `enso_now`; read ONI only to count
disagreements for `data_gaps`. Not an `mvp.yaml` variable (context for plan-risk, not a scoring
variable). Next: `/new-source noaa_enso` → `app/integrations/noaa_enso.py` with `parse_enso_index`,
its own cache namespace, a monthly cache key and a cached fallback.
