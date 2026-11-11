# ADR-0012: Noise-aware verdicts vs. seasonal-naive, surfaced in the UI and README

- **Status:** Accepted
- **Date:** 2026-11-11
- **Change:** `improve-forecasting-evaluation-and-inventory`
- **Refines:** rolling-cv-evaluation spec "Baseline comparison"; design.md decision 3

## Context

Prophet stays the production model. Seasonal-naive is a strong baseline for daily family totals with weekly patterns, so Prophet will sometimes lose. Headline metrics come from only 3 test folds (ADR-0007), so small skill differences are noise.

## Decision

- **Verdict per product × horizon bucket**, from test folds:
  - `beats`: skill ≥ +5% **and** Prophet wins in ≥ 2/3 test folds;
  - `worse`: skill ≤ −5% **and** Prophet loses in ≥ 2/3 test folds;
  - `comparable`: otherwise.

  Thresholds are config (`VERDICT_SKILL_THRESHOLD`, `VERDICT_MIN_FOLD_SHARE`).
- **Accuracy panel:** a badge for the bucket(s) covered by the requested horizon, and a plain-language note when the verdict is `worse`.
- **Inventory panel:** if the 1–7 bucket verdict is `worse`, a warning next to the reorder point. Recommendations are never suppressed.
- **Forecast chart:** seasonal-naive forecast drawn as a faint reference line.
- **README findings:** verdict counts per bucket across Favorita products, plus the pooled achieved service level (ADR-0008).

## Alternatives considered

- **Raw skill only:** invites over-reading noise.
- **Suppress recommendations when the verdict is `worse`:** hides the result we want to be honest about.

## Consequences

- The API returns `verdict` per bucket in `GET /api/accuracy/<id>` and the 1–7 verdict in `GET /api/inventory/<id>`.
- The forecast endpoint also returns the seasonal-naive series for the displayed horizon. It is computed on read from history, not persisted.
