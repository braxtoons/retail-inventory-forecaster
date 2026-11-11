# ADR-0008: Cycle service level; lead-time demand from Prophet sample paths

- **Status:** Accepted
- **Date:** 2026-11-11
- **Change:** `improve-forecasting-evaluation-and-inventory`
- **Supersedes:** design.md decision 6 (σ from interval width combined by √Σσ²)

## Context

Design decision 6 derived daily σ from the 95% interval and combined it over the lead time as √Σσ², while claiming no independence shortcut. √Σσ² *is* the independence assumption. Prophet's daily errors are positively correlated (trend/level error persists), so this understates lead-time uncertainty, and safety stock comes out too low. "Service level" was also undefined.

## Decision

- **Service level means cycle service level (α):** P(lead-time demand ≤ reorder point). Valid range (0.5, 0.999); default 0.95 (lead time default 7 days).
- **Lead-time demand distribution:** `model.predictive_samples(future)` with `uncertainty_samples = 1000` (config) and a **fixed random seed** per run. For each sample path, clip daily demand at 0 and sum days 1..L.
- **Reorder point** = α-quantile of that distribution.
- **Safety stock** = reorder point − mean lead-time demand (path mean of the clipped sums).
- **Calibration check:** on CV test folds (ADR-0007), record whether actual lead-time demand ≤ the forecast α-quantile. Report the **achieved cycle service level**, pooled across products, in the README and the accuracy panel, next to the target α.

## Alternatives considered

- **√Σσ² from interval widths, labelled as assuming independence:** simplest, but known to understate risk.
- **Empirical lead-time residual quantiles from CV:** only about 13 folds per product is too few for a 95% quantile without pooling across products. Kept as a possible refinement once calibration data exists.

## Consequences

- Monotonicity in α (spec scenario "Higher service level") holds by construction: quantiles of one fixed sample set are non-decreasing in α. Tests must use a fixed seed.
- Sample paths must be persisted with the forecast run (or the run must be refittable deterministically) so `GET /api/inventory/<id>` does not retrain. Persisting per-day lead-time sums is enough: 1000 × 90 values per run at most, or store cumulative-sum quantiles only. See the persistence decision.
- Prophet intervals are often too narrow. The calibration check is how we find out, and the README must report it honestly even if achieved < target.
- Lead time must be ≤ 90 days (the maximum horizon, ADR-0005).
