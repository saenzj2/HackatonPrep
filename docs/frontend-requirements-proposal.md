# Farmer-facing front-end requirements proposal

**Status: proposed design for discussion, not an implemented UI, approved scope, or API contract.**
The intended user is a farmer or agricultural advisor exploring feasible rotations for a location.
Ask only for information people know; use available evidence honestly and explain uncertainty.
The [input proposal](farmer-input-proposal.md) details evidence and units. This document does not
change backend behavior, configuration, scoring or the [current contract](../backend/docs/api-contract.yaml).

## 1. Product scope and principles

Help people identify a location, describe optional existing practices, express priorities and
constraints, and compare explained options. Preserve both paths: **no current crop** and **a
farmer-reported current or recent crop**. Offer alternatives only when evidence and rules support
them. The hypothetical pineapple scenario in San Carlos is one example, not exclusive product
scope or a confirmed crop. Provide mobile-first, keyboard-usable, plain-language interactions;
label observations, models, rules, source periods, uncertainty and missing information.

## 2. Proposed screen inventory

Names and routes below are design candidates, **not existing routes or an approved implementation**.

| Screen | Example route | Purpose and controls |
|---|---|---|
| Welcome | `/` | Explain purpose, start planning, how it works and sources. |
| Location | `/farm/location` | Map, optional place search, permission-based GPS, manual coordinates and optional area. |
| Farm profile | `/farm/profile` | Optional current crop/history, proposed planting season, soil and management. |
| Resources | `/farm/resources` | Irrigation, water availability, available/excluded crops and optional budget. |
| Preferences | `/plan/preferences` | Priorities or normalized weights, proposed horizon and risk preference. |
| Results | `/results` | Ranked options, seasonal timeline, caveats and available evidence. |
| Compare | `/compare` | Side-by-side trade-offs, optional scenarios and sensitivity. |
| Methodology | `/help` | Sources, assumptions, glossary and FAQs. |

## 3. Journey and state

Proposed journey: Welcome → Location → Profile → Resources → Preferences → Results → Compare →
revise. Use a stepper and Back/Next; offer Save Draft **only if persistence is implemented**.
Retain entered values while navigating. Distinguish user observations from estimates and allow
explicit overrides without destroying provenance. When location or relevant crop history changes,
mark dependent results stale and request regeneration. Show loading, empty and error states;
GPS denial must leave manual coordinates and, if implemented, place search available.

Prefer suitable cached evidence first. Fetch external data only where available and explicitly
configured/authorized within provider budgets; do not silently fall back to live, mock or fabricated
values. A cache miss should explain what is unavailable and offer retry or manual input where
supported. The [cache policy](../PROJECT_CONTEXT.md#cache-first-direction-and-quota-boundaries)
is a proposed direction, not a claim that the current live mode is cache-first.

## 4. Candidate input controls and validation

Statuses below are **proposals**, except location is required by today's recommendation request.
No-current-crop and unknown-history users must be able to reach a meaningful exploration without
inventing a baseline. Any new mandatory input or request field needs team agreement and a
contract-first change. Group advanced details under “Improve my recommendation.”

| Field | Proposed status | Validation / interaction |
|---|---|---|
| Location | Required | Map point or manual latitude −90..90 and longitude −180..180; optional search/GPS with consent. Bound analysis to supported region where applicable. A rectangle is an analysis zone, not a verified farm boundary; today's API accepts a representative point, not an area average. |
| Farm area | Optional | Positive number, hectares/acres with unit conversion and help. |
| Current or most recent crop | Optional / unknown | Search supported crops; “none,” “unknown” and “other” must not silently substitute a crop. Report unsupported crops as gaps. |
| Past crops | Recommended, skippable | Crop + season/year for 2–3 previous seasons; reject duplicate season entries unless intercropping is explicitly supported. Do not invent history. |
| Planned planting season | Proposed essential, pending agreement | Date/month or window, appropriate to local calendar and hemisphere; explain when missing. Not currently an API-required field. |
| Soil texture and pH | Optional | Unknown supported; pH 0–14; clearly distinguish laboratory values from estimates and capture date/depth/method where known. |
| Soil organic carbon | Optional | Require unit, depth and measurement method when supplied; distinguish concentration from carbon stock. |
| Tillage / cover crops | Optional | Conventional/reduced/no-till/unknown; cover use yes/no/unknown with optional species. |
| Irrigation and water | Proposed essential, unknown allowed | Rainfed/drip/sprinkler/other/unknown and limited/variable/sufficient/unknown; optional seasonal allocation with volume or depth units, time and area. Never infer zero from unknown. |
| Allowed / excluded crops | Recommended, skippable | Show constraints and do not recommend excluded species once supported; disclose conflicting or unsupported selections. |
| Main priority and horizon | Proposed essential, pending agreement | Goal or normalized weights; propose 2/3/5-year horizon and state seasons/year. Current API supports water/soil/climate weights, not these planning horizons. |
| Budget and risk | Optional | Budget requires currency, total or per-area basis and period; risk low/medium/high. |

## 5. Context-sensitive behavior

- On location selection, show available cached climate and soil evidence, source and freshness;
  retrieve other evidence only where authorized and supported. Soil estimates are not currently
  integrated, and backend soil pH/moisture remain mock. A missing estimate must remain unavailable.
- Rainfed hides irrigation hardware/allocation unless expanded; irrigated may show optional seasonal
  water and system efficiency. Water priority may reveal tighter limits or seasonal drought concerns.
- An unsupported crop must be named as unsupported and preserved as a user report; only offer a
  rules-only option if such a method actually exists and is clearly labeled, otherwise unavailable.
- Changing location, crop history or constraints invalidates dependent recommendations.

## 6. Recommendations

A proposed presentation is up to three feasible candidates with year/season, crop and any cover-crop
phase in a timeline. This is a design target, not an assertion that the current API guarantees three:
`top_n` controls the returned list and an optional baseline may be separate. Explain why each option
ranks, violated preferences, assumptions, trade-offs and data gaps. Provide Compare, Change
priorities and Edit farm information actions. Prominently warn when evidence is insufficient.

Show productivity, water demand/stress, soil-protection proxy and climate robustness **only when
supported**, each labeled prediction, estimate, rule-based or unavailable with units and uncertainty.
Suitability is not yield, water volume or measured soil improvement. Do not present changes in soil
carbon or multi-year yield as proven outcomes without relevant validated models. No crop is confirmed
from the San Carlos imagery; pineapple is not a configured/validated recommendation case.

## 7. Comparison and simulation

- **Side-by-side:** use the same units and time horizon for all options.
- **Climate scenarios:** compare a historical baseline with projections only if available and
  appropriately labeled, with model/scenario and uncertainty. No forecast claim.
- **Priority adjustments:** sliders/presets normalize weights to 100% and state what the current
  model supports; do not imply unsupported objective categories are implemented.
- **Trade-offs and robustness:** show what improves or worsens against a selected baseline without
  false precision, and explain any rank changes across available scenarios.
- **Optional export/sharing:** a human-readable PDF/CSV could include the plan, assumptions, sources
  and timestamp; no export or persistence is assumed implemented.

## 8. Visual prototype reference

The user referred to an illustrative farmer-intake prototype, but no matching reference asset was
provided with this specification. Do not invent or imply a final wireframe. Future designs should
follow the validated field, accessibility and transparency requirements agreed by the team.

## 9. Validation, empty and error states

- Missing an agreed required input: inline guidance, preserve other values; for example “Select a
  planting season to continue” **only if that field becomes required**.
- Invalid latitude/longitude: focus the field and explain the accepted range.
- NASA/source failure: identify the source, explain missing data and provide retry/manual fallback
  where implemented; never turn missing values into zero or silently fabricated estimates.
- All feasible crops excluded: show the conflict and let the farmer revise constraints.
- No viable rotation: show known binding constraints and settings that could be reconsidered.
- Insufficient evidence: show a prominent warning and limit numerical claims.

## 10. Non-functional targets

- **Responsive:** usable from approximately 360 px mobile through desktop; tables scroll or become cards.
- **Accessibility:** target [WCAG 2.2 AA](https://www.w3.org/TR/WCAG22/): semantic labels, keyboard
  navigation, focus visibility, contrast and non-color-only indicators. This is a target, not a
  claim of current compliance.
- **Performance/reliability:** lazy-load heavy maps/charts, show loading skeletons, debounce location
  queries, cache eligible reference data and degrade gracefully offline or during API failures.
- **Internationalization:** externalizable strings, localized dates/numbers and hectares/acres and
  mm/m³ handling with explicit conversion context.
- **Privacy:** explain location permission; minimize precise-coordinate collection, and disclose
  consent and retention where accounts/persistence exist. Tooltips and provenance support explainability.

## 11. Proposed interfaces, not live endpoints

| Suggested interface | Intended responsibility |
|---|---|
| `POST /api/farms/profile` | Location, area, history, observations/overrides and management. |
| `GET /api/environment?lat=&lon=` | Historical climate, soil estimates, coverage, sources, units and errors. |
| `POST /api/rotations/recommend` | Profile, constraints, horizon and normalized priorities. |
| `POST /api/rotations/compare` | Candidate IDs and scenarios; comparable metrics and uncertainty. |

Response metadata should carry per-metric source, observation/retrieval time, units, evidence type,
assumptions, uncertainty and warnings. These paths are proposed examples, **not current live routes**.
The existing point-based API includes `POST /recommendations` and `GET /conditions`; see the
[current contract](../backend/docs/api-contract.yaml). Add/change a contract only after frontend and
backend agreement, then implement and test it.

## 12. Proposed MVP acceptance

- Locate the analysis area without requiring browser GPS; explain that a point is not a parcel average.
- Complete and revise essential inputs without losing in-session state; do not require a current crop.
- Label weather and any available soil sources; allow overrides only where implemented and preserve
  provenance. Soil is currently mock; no live soil lookup is promised.
- Validate agreed required fields, ranges and contradictory supported crop constraints.
- Render supported candidate rotations with seasonal timelines, provenance and evidence categories;
  distinguish modeled, rule-based and unavailable metrics.
- Compare options and observe supported priority changes; no baseline when none is supplied.
- Missing data and source failures show actionable messages, never misleading zeroes/defaults.
- Validate critical flows on mobile and keyboard; no compliance claim until tested.

## 13. MVP versus future: scope proposal

| Candidate MVP | Future enhancement, dependent on data and agreement |
|---|---|
| Anonymous guided location and farm input; in-session edits | Accounts, saved farms and shared plans |
| NASA weather and **available** soil context, clearly labeled manual/mock fallback | Additional soil services, local sensors, offline field operations |
| Rule-guided supported crop rotations, ranked comparison and source labels | Validated multi-year biophysical simulation, localized calendars and multilingual delivery |
| Plain-language reasons, gaps and warnings | Interactive risk-scenario and sensitivity analysis, export and sharing |

These are suggestions, not a commitment to implement all items during the hackathon. A small
end-to-end demo with honest gaps takes precedence over unvalidated functionality.

## 14. External references and evidence boundary

- [NASA POWER](https://power.larc.nasa.gov/) and [daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/).
- [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg).
- [ISRIC SoilGrids documentation](https://docs.isric.org/globaldata/soilgrids/).
- [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/).

User-supplied requirements propose a design, not proof of an implemented or validated service.
Experimental yield-response data alone does not validate optimal multi-year rotations, long-term
soil health, farm-specific yield or water savings. Require fit-for-purpose data, agronomic evidence,
local evaluation and uncertainty disclosure before making such claims.
