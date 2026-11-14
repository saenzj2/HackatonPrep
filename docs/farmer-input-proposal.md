# Farmer intake and evidence proposal

**Proposal, not an implementation commitment.** This records the farmer-input suggestions in
[issue #73](https://github.com/saenzj2/HackatonPrep/issues/73). Keep both entry paths: a farmer
without a current crop can explore, and a farmer with an existing crop can optionally supply it.
No real farmer, field measurements or validated agronomic recommendation is available for this
scenario. This document changes no code, configuration, scoring or API contract.

## What exists today

Source/configuration inspection: **14 November 2026**, not a runtime acceptance test.

| Existing boundary | Evidence and implication |
|---|---|
| Required request fields | Only `lat` and `lon` in [the contract](../backend/docs/api-contract.yaml), `RecommendationRequest`. The API analyzes a point, not an area. |
| Optional request fields | `crops`, `priorities`, `top_n`, `current_rotation`; omitted crops/priorities use configured defaults. Current crop is NOT required. |
| Baseline comparison | `current_rotation` needs one supported crop per configured season. It is not an arbitrary single current crop or a 2–3-season history. Without it, baseline and score deltas are null. |
| Configured MVP | [mvp.yaml](../backend/config/mvp.yaml) selects rice, beans and maize; `primera`/`postrera` repeat annually, with dry-season fallow. This is not a 2/3/5-year optimizer. Region remains provisional. |
| Current evidence | [Services](../backend/app/services.py) use monthly climate for recommendations; the daily adapter is not a daily heat/drought recommendation model. [Source registry](../backend/app/integrations/__init__.py) uses mock soil in every mode. Catalog values are unverified. |
| Current results | Ranked rotations, scores/category breakdown, explanations, benefits, risks, gaps and evidence. These are heuristic suitability comparisons, not yield, profit, measured water savings or soil recovery. |

The [shared context](../PROJECT_CONTEXT.md#farmer-first-map-direction-not-implemented-here) describes
the agreed two-path direction. Do not guess existing crops from an image, silently replace an
unsupported crop, or manufacture a baseline. The San Carlos example remains hypothetical.

## Proposed intake inventory

**All additions below are candidates pending design agreement.** “Optional” and “unknown” are
proposed user-experience behavior, not new API fields. Location coordinates are the only existing
required inputs; decide any additional required fields explicitly with the team.

| Section | Proposed fields | Disclosure and unresolved choices |
|---|---|---|
| 1. Location | Country/region; map-selected coordinates; optional area with hectares or acres | Confirm location in both paths. Country/region are context, not current request fields. Rectangle/polygon support and representative-point rules remain pending; never label a point value an area average. Preserve entered area unit. |
| 2. Crops and timing | Optional current or recent crop; optional previous 2–3 seasons, crop per season and dates; intended planting season | Allow no crop, unknown history and skipped baseline. Distinguish current crop, recent crop, history and candidate crops. Agree mapping to seasonal baseline before sending `current_rotation`; do not invent missing seasons. |
| 3. Soil and management | Texture, including unknown; tillage practice; cover-crop use; optional soil tests including pH and soil organic carbon (SOC) | Reveal tests only when available. Record test date, depth, method and units: pH method; SOC concentration (e.g. g/kg) versus stock (e.g. t C/ha, with depth). Never treat these as interchangeable. Tillage/cover crop may also be unknown. |
| 4. Irrigation and water | Rainfed/irrigated/unknown; irrigation type; seasonal water availability; optional volume | Reveal type/volume only when applicable. Volume needs quantity, unit (e.g. m³), time window, and area if converting to depth. Do not infer zero available water from a skipped field. |
| 5. Goals and constraints | Main priority; planning horizon of 2, 3 or 5 years; available/preferred and excluded crops; budget; risk tolerance | Water/soil/climate map to existing priority categories only after agreed UI-to-weight mapping. Other goals, exclusions, budget and risk have no current request fields. Budget needs currency, period and total/per-area basis. Horizon is not a climate forecast. |

### Progressive disclosure: proposed 10-prompt first pass

This is a UX sketch, not a mandatory questionnaire. Prompts can group related controls; optional
follow-ups expand only when relevant. Eight prompts may suffice when soil tests and constraints
are skipped. Completion rules, defaults and exact wording still need agreement.

1. Confirm country/region and location on the map; optionally add area and unit.
2. Optionally describe current/recent crop, or choose no current crop/unknown.
3. Optionally add the last 2–3 seasons; select intended planting season if known.
4. Describe soil texture, or choose unknown.
5. Describe tillage and cover-crop use, or choose unknown.
6. Optionally add available soil tests and their metadata.
7. Describe irrigation and water availability; optionally add volume, unit and period.
8. Select the main goal and proposed 2/3/5-year planning horizon.
9. Optionally identify available/preferred and excluded crops.
10. Optionally describe budget and risk tolerance.

The no-current-crop path must reach evidence and candidate comparisons without prompts 2–3
becoming blockers. The existing-crop path must preserve the reported crop even when unsupported,
explain the gap and avoid claiming single-crop advice the current API does not provide.
Do not send proposed extra fields to the strict current request schema.

## Suggested automatic evidence, with gates

Provider documentation checked **14 November 2026**. Documentation availability is not proof of
successful pilot data acquisition, completeness, cache readiness or an implemented integration.
Use suitable labeled cache first; acquisition requires separately agreed source/location/budget.

| Candidate | Verified source boundary | Proposed use and unresolved work |
|---|---|---|
| Historical temperature and rain | [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) documents daily meteorological series at source-grid resolution. | Explore daily maximum-temperature thresholds and dry-spell/drought indicators; agree crop thresholds, baseline, period, missing-data rules and validation. Derived indicators are not direct drought observations; current monthly scores do not count daily extremes. |
| Climate scenarios | The supplied [POWER Projection API documentation URL](https://power.larc.nasa.gov/docs/services/api/projection/) loads successfully and documents NEX-GDDP-CMIP6-derived daily/monthly projections, 2015–2100, 0.25° grid and scenario/model selection. | A documented service, not an implemented backend source or a verified pilot response. Confirm actual data availability, units, model/scenario, missing values and request limits before use. Scenario projections are conditional climate evidence, not deterministic farm weather forecasts. Do not substitute the historical endpoint or infer reliability over a 2–5-year farm plan. |
| Soil texture and pH | [ISRIC SoilGrids documentation](https://docs.isric.org/globaldata/soilgrids/) lists pH, texture fractions and SOC maps at 250 m, six depth intervals, prediction uncertainty and CC-BY 4.0. It explicitly announces a temporarily paused REST API, with no restoration date. | Candidate fallback estimates only. Prefer relevant, quality-checked farmer measurements while retaining their provenance and conflicts with mapped estimates. Agree depth, unit conversions and texture-class method; verify local availability/access route. WCS/WebDAV are documented alternatives, not acquired data. No new heavy dependency or soil integration is approved. |
| Water-balance screening | [FAO-56 introduction](https://www.fao.org/4/x0490e/x0490e04.htm) distinguishes reference ET and crop ET, and expresses ET in mm per time unit. | A proposed `precipitation − ET` indicator must name the ET definition/method, rainfall treatment, same location/time window and units (e.g. mm/season); sum compatible daily quantities. It is not irrigation demand: storage, runoff, drainage, effective rain and irrigation efficiency need explicit assumptions. No guaranteed savings. |
| Crop requirements and rotation compatibility | Current [EcoCrop subset](../backend/data/ecocrop_subset.csv) and source citations are a starting inventory, not validated local recommendations. | Verify sourced temperature/water/pH ranges, crop cycle, family, management and local calendar. Explicit compatibility evidence is needed before asserting nitrogen, pest or soil benefits; do not turn placeholder bonuses into measured effects. |
| Experimental yield model | No calibrated yield model or farmer outcome dataset is established here. | Research only, outside the current MVP. Requires suitable training/evaluation data, local calibration and independent validation before any operational yield or uncertainty claim. No model/library choice is approved. |

Every future layer/result should show provider/product, acquisition and observation dates, spatial
and temporal resolution, units, depth where relevant, uncertainty, missing values and mock status.
Coarse mapped estimates are not field measurements; no automatic source can silently fill a
farmer's crop history or preferences. Follow the repository's fixture/source-page readiness rules
before integrating a new source.

## Proposed farmer-facing output

Lead with one explained option, then comparable alternatives **when evidence supports them**.
The existing `top_n` response is not a promise of exactly three strategies.

| Desired output | Status and honest presentation |
|---|---|
| Rotation sequence and alternatives | Current API supports seasonal ranked sequences. Multi-year 2/3/5-year scheduling is pending design, not current functionality. Show unsupported crops or absent evidence as gaps. |
| Expected yield and interval | Research only. Show no numeric yield or confidence interval unless a validated model supports the estimand, units (e.g. t/ha/season), evaluation and interval coverage. Distinguish confidence intervals from prediction intervals; suitability score is neither. Otherwise say unavailable. |
| Water demand | Not currently calculated. A future estimate needs method, units, period, irrigation assumptions and evidence; a water suitability score is not volume or savings. |
| Soil protection | A possible explicitly labeled proxy, with sourced rules and limitations, not measured SOC gain, soil recovery or erosion reduction. No accepted proxy is established here. |
| Climate robustness | Current climate suitability is heuristic. Scenario/stress sensitivity would need agreed inputs, comparisons and validation; do not present it as a probability of resilience. |
| Why, risks and tradeoffs | Existing explanation/benefits/risks/gaps/evidence can support a plain-language comparison. Baseline deltas appear only when the farmer supplied a valid seasonal baseline. Explain uncertainty and what would change the ranking. |

**Illustrative story only:** a diagram might show maize → soybean → sorghum across imagined
periods. This is not an agronomic recommendation, a validated crop combination or configured MVP
scope. Only maize is among the configured `rice`, `beans`, `maize` candidates. Do not send that
three-crop story as the two-season `current_rotation`, or add crops/configuration to make it fit.

## Decisions still required

- Agree the first-pass prompts, required-versus-optional rules, unknown handling and priority mapping.
- Agree how a single current crop/history relates to the seasonal baseline, and whether a multi-year
  planner is needed; neither is authorized by documenting the idea.
- Select the smallest useful evidence chain; confirm local crop/calendar suitability and source
  availability, units, caching and acquisition limits before promising a result.
- Separately approve any contract-first implementation and record accepted technical choices in
  [decisions.md](../backend/docs/decisions.md). No decision is inferred from this inventory.

**Outside this documentation task:** API/UI implementation, changed required fields, new
integrations or acquisitions, real-farmer validation, scoring changes, economic optimization,
calibrated yield/soil/water models and operational recommendations.
