# ADR-0002: Rolling CV builds each fold's future with production's regressor assumptions

- **Status:** Accepted
- **Date:** 2026-11-11
- **Change:** `improve-forecasting-evaluation-and-inventory`
- **Supersedes:** design.md decision 2 (`prophet.diagnostics.cross_validation` as primary path), and amends decision 5

## Context

`prophet.diagnostics.cross_validation` predicts each fold using the **actual** historical values of every regressor column. Production does not have those values for the future: oil is unknown, and promotions are only known where planned. Using Prophet's CV as designed would score regressors using information production lacks. The ablation would then favour those regressors, and the reported accuracy would overstate what ships.

## Decision

1. **Custom rolling-origin loop.** Cutoffs come from `prophet.diagnostics.generate_cutoffs` (same `initial`/`period`/`horizon` semantics). For each cutoff the loop fits `build_model(config)` on history up to the cutoff, then builds the future frame with the **same function production uses** (`build_future_frame(history, horizon, as_of=cutoff)`), and predicts.
2. **Regressor knowledge policy**, applied identically in production and CV:

   | Regressor | Known in advance? | Future value |
   |---|---|---|
   | Holidays | Yes (calendar) | Prophet `holidays` dataframe |
   | Promotions | Yes, where planned | Planned promotions; 0 where none planned |
   | Oil price | No | Last value at or before the cutoff, carried forward |

3. **Planned promotions** are stored in a new `planned_promotions(product_id, date, on_promotion)` table, seeded from Kaggle `test.csv` (2017-08-16 → 2017-08-31). In CV, actual historical promotions stand in for "planned", because in this domain promotions are planned ahead.
   Planned promotions are **seed-only**: there is no write API or UI editor. A what-if promo editor is a possible follow-up, and would need edits to mark the latest forecast run stale (ADR-0010).
4. Forecast responses carry `promo_known_through: <date>`. Beyond that date promo defaults to 0, and the forecast is expected to under-predict on promotion days. This is surfaced, not corrected.

## Alternatives considered

- **Prophet's built-in CV, relabelled "accuracy given known regressors":** cheap, but it reports an upper bound rather than expected accuracy, which defeats the change's purpose.
- **Drop oil and promo, keep holidays only:** simplest, but removes the ablation the owner wants.
- **Promo assumed 0 (or carried forward) in production:** honest but discards a strong, genuinely known-in-advance signal.

## Consequences

- We own the CV loop: parallelism, fold capping and correctness tests are ours (`cross_validation`'s `parallel=` option no longer applies directly).
- A test must assert that for a given cutoff, CV and production produce identical future frames.
- Oil's CV score now reflects carry-forward, so the ablation will likely drop it. That is the intended, honest outcome.
- The spec scenario "Same configuration as production" is extended to cover future-frame construction, not just the model factory.
