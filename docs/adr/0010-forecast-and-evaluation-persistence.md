# ADR-0010: Persistence model: full-horizon forecast runs with stored sample paths; evaluation runs carry the selected config

- **Status:** Accepted
- **Date:** 2026-11-11
- **Change:** `improve-forecasting-evaluation-and-inventory`
- **Supersedes:** design.md decision 7 table list; tasks.md 1.3 (`product_model_config` table)

## Context

Inventory recommendations (ADR-0008, ADR-0009) need demand sample paths at read time. Caching per requested horizon would miss whenever a different horizon or lead time is requested. Forecasts made with the default configuration go stale once evaluation selects a different one.

## Decision

- **Every forecast run computes the full maximum horizon (90 days).** `forecast_days` (1–90) only limits what is returned and shown.
- **Schema (additive migration):**
  - `forecast_runs(run_id PK, product_id FK, created_at, as_of_date, config JSONB, config_source TEXT CHECK IN ('selected','default'), seed INT, promo_known_through DATE, data_fingerprint TEXT)`
  - `forecasts` gains `run_id FK → forecast_runs ON DELETE CASCADE`. Per-day `predicted_quantity`, `lower_bound`, `upper_bound`. The "delete all forecasts for product" behaviour is removed.
  - `forecast_run_samples(run_id PK FK ON DELETE CASCADE, cumulative_paths REAL[][])`: 1000 × 90 **cumulative** demand paths (daily values clipped at 0 before accumulating).
  - `evaluation_runs(eval_id PK, product_id FK, created_at, cv_params JSONB, training_start DATE, data_fingerprint TEXT, selected_config JSONB)`. The current selected configuration = the latest evaluation run for the product. **No separate `product_model_config` table.**
  - `evaluation_metrics(eval_id FK, model TEXT, arm TEXT NULL, fold_cutoff DATE, fold_set TEXT CHECK IN ('selection','test'), horizon_bucket TEXT, mae, rmse, wape, mape, mape_excluded INT, coverage, n INT)`
  - `evaluation_service_level(eval_id FK, fold_cutoff DATE, lead_time INT, alpha NUMERIC, hit BOOLEAN)` for the calibration check.
- **Writes are atomic:** run, daily rows and samples are inserted in one transaction (`execute_values`), which also **prunes runs beyond the latest 5 per product**. Evaluation runs are kept.
- **Staleness:** `GET /api/forecast/<id>` returns `stale: true` and `stale_reason` when the run's `config` ≠ the current selected configuration, or its `data_fingerprint` ≠ the current data. Reads never train. The UI offers Regenerate.
- **`GET /api/inventory/<id>`** with no forecast run returns `404` "generate a forecast first".

## Alternatives considered

- **Quantile grid instead of raw paths:** smaller, but tail quantiles (α up to 0.999) and arbitrary on-hand probabilities need fine resolution. Raw paths are exact and simple. Size is about 360 KB/run × 5 runs × 33 products ≈ 60 MB worst case.
- **Auto-regenerate stale runs on read:** brings back reads that train.
- **Per-horizon runs:** cache misses on different horizons or lead times.

## Consequences

- The forecast-persistence spec's "Cached read" scenario holds for any `forecast_days` ≤ 90 and any lead time ≤ 90.
- `data_fingerprint` is computed identically by forecast and evaluation code (shared helper).
- The frontend must handle `stale`, `config_source` and the inventory 404.
