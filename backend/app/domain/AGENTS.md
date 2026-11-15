# app/domain/AGENTS.md: pure decision logic

The heart of the product: given climate, soil and crop data, score crops per season and rank rotations.
General backend rules: [`backend/AGENTS.md`](../../AGENTS.md).

## Files
- `models.py`: frozen dataclasses (`Range`, `CropProfile`, `MonthlyClimate`, `SoilConditions`, `Season`,
  `Weights`, `CropSeasonFit`, `RotationResult`). Validate invariants in `__post_init__`.
- `suitability.py`: trapezoid scoring per variable → categories (climate, water, soil) → one crop/season score.
- `erosion.py`: slope → terrain risk, daily rain → rainfall risk, combined erosion risk (0/1/2).
- `soil.py`: derived soil values (`silt_pct` from clay and sand, only when plausible).
- `indicators.py`: daily series → monthly indicators (rain, dry spells, extremes; heat/frost only from true max/min).
- `planting_windows.py`: best sowing months per crop (each month scored over the crop's cycle with
  `crop_season_fit`), grouped into windows. Extra info; rotations still use the configured seasons.
- `rotation_rules.py`: one crop after another → verdict (favoured / allowed / discouraged), reasons, score
  adjustment. Add a rule: one function + one entry in `RULES`.
- `ranking.py`: builds every rotation, applies the rotation rules to each pair, sorts, writes the explanation.

## Rules
- **Pure.** No I/O, no network, no files, no logging, no clock, no randomness. Same input → same output,
  always. This is what makes the logic easy to test and to explain to judges.
- **Errors.** Impossible inputs raise `DomainInvariantError` (a bug upstream, → 500). User-fixable
  problems are validated before the domain is called (`services.py`), not here. See `docs/errors.md`.
- **Imports.** Only the standard library, other `app.domain` modules and `app.errors`. Never `app.api`,
  `app.integrations`, `app.services`, `app.settings`, FastAPI, Pydantic or httpx.
- **Plain types in, plain types out.** Domain dataclasses, not dicts or Pydantic models.
- **Units are already normalized** (see backend/AGENTS.md). If you need to convert a unit here, the
  conversion belongs in the adapter instead.
- **Scores are floats in 0..1.** Clamp at the end, round only for output (4 decimals).
- **Explainability over precision.** Each rule should be explainable in one sentence to a farmer.
  When you add a rule, add a matching `notes` message so the response can say why a score moved.
- **Keyword-only arguments** for functions with many inputs (`rank_rotations(*, crops=..., ...)`).
- **Placeholders are named constants** at the top of the module, with a comment. Changing their values
  needs a `docs/decisions.md` entry and ideally an `agro-logic` review.

## Testing
`tests/test_domain.py`. Build tiny `CropProfile`s inline with round numbers so the expected score
is obvious by hand. Cover the edges: exactly at `abs_min`, `opt_min`, `opt_max`, `abs_max`, and a variable disabled in config.
