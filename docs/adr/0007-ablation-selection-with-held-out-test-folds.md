# ADR-0007: Regressor ablation selects on earlier folds; headline metrics come from held-out recent folds

- **Status:** Accepted
- **Date:** 2026-11-11
- **Change:** `improve-forecasting-evaluation-and-inventory`
- **Refines:** design.md decision 4; rolling-cv-evaluation spec "Regressor ablation" and "Sufficient/Insufficient history"

## Context

Picking the best of 5 ablation arms on a set of folds and then reporting that arm's score on the same folds overstates accuracy (selection bias). The spec also did not say which WAPE drives selection or how the minimum-improvement margin works.

## Decision

- **Fold split** (about 13 cutoffs, ADR-0005):
  - **Test folds:** the last 3 cutoffs (≈ 2017-01 → 2017-05).
  - **Selection folds:** earlier cutoffs whose 90-day window ends on or before the first test cutoff (about 9).
  - Folds whose windows overlap the test period are dropped.
- **Selection** uses selection folds only. Metric: overall WAPE, days 1–90.
- **Rule:** start from holidays-only. A change of arm (adding promo, adding oil, or removing holidays) is accepted only if it lowers selection WAPE by **≥ 2% relative** (`ABLATION_MIN_REL_GAIN`) **and** wins in **≥ 2/3 of selection folds** (`ABLATION_MIN_FOLD_WIN_SHARE`). Arms are compared greedily from the base: add the best qualifying regressor, then test adding the next one.
- **Headline metrics** (Prophet with the selected configuration, naive, seasonal-naive, skill vs. seasonal-naive, interval coverage) come **only from test folds**. The full ablation table is reported and labelled "selection folds".
- **Minimum history:** enough for 3 test folds plus 3 selection folds. Products below it are skipped by the evaluation CLI, with a report. The API returns the "not evaluated" response for them.

## Alternatives considered

- **Select and report on the same folds, labelled optimistic:** simpler, but the bias would be unmeasured, which defeats the change's aim.
- **Select on 1–7-day WAPE:** fits inventory, but production forecasts span up to 90 days.

## Consequences

- Only 3 test folds feed the headline numbers, so they are noisy. The UI and README show per-fold values, not just the mean.
- Test folds lie in 2017 only, so the headline reflects recent behaviour, which is what a forecaster cares about.
- Evaluation fits = 5 arms × selection folds + 1 selected config × test folds (≈ 48 fits per product), a little under the earlier estimate.
