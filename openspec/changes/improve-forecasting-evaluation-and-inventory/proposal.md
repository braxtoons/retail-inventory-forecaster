## Why

The current accuracy metric is unsound. It trains a Prophet model without the regressors used in production, uses a single 80/20 split, and has no baseline, so reported MAE/MAPE cannot show whether the model is any good. The training data is also corrupted: the holiday join double-counts sales on dates with two national holiday rows, transferred holidays are treated as days off, and weighed products are truncated to integers. The app is called an "inventory" forecaster but never turns forecasts into inventory decisions, retrains Prophet on every request, and has no tests or reproducible setup.

Terms used below are defined in [`CONTEXT.md`](../../../CONTEXT.md); decisions are recorded as ADRs in [`docs/adr/`](../../../docs/adr/).

## What Changes

- **Domain framing:** a *product* is a product family aggregated across stores; inventory is held at a single notional *distribution centre*. Weighed families keep fractional quantities (ADR-0001).
- **Data correctness:**
  - Build a Prophet `holidays` frame from Kaggle holiday types with explicit mapping rules (drop transferred originals, keep transfers, bridges, work days, recurring events). One-off *shock events* (2016 earthquake, 2014 World Cup) are modelled separately.
  - Remove the sales/holiday join that double-counts sales (ADR-0004).
  - For Favorita, train from 2014-04-01 (promotion data is unrecorded before then) and treat closure days as missing (ADR-0003).
- **Rolling CV that scores what ships:** a custom rolling-origin loop builds each fold's future frame with the same function and *regressor knowledge policy* as production. Holidays come from the calendar, promotions from planned promotions, and oil is carried forward (ADR-0002).
- **Horizon and buckets:** maximum forecast horizon of 90 days. Evaluation runs at 90 days and reports metrics per *horizon bucket* (1–7, 8–30, 31–90) (ADR-0005).
- **Honest model selection:** a greedy regressor ablation on *selection folds* (≥ 2% relative WAPE gain and ≥ 2/3 fold wins). Headline metrics come only from 3 held-out *test folds* (ADR-0007).
- **Baselines and verdicts:** naive and seasonal-naive on identical folds. MAE, RMSE, WAPE (headline), zero-safe MAPE and interval coverage. A noise-aware *verdict* vs. seasonal-naive (`beats`/`comparable`/`worse`) is surfaced in the UI and README (ADR-0012).
- **Inventory recommendations:**
  - *Cycle service level* semantics. Reorder point = α-quantile of lead-time demand from Prophet joint sample paths. Safety stock = ROP − mean (ADR-0008).
  - Stock-out probability, risk levels tied to α, `reorder_now`, and projected stock-out dates (ADR-0009).
  - Calibration reported as achieved service level.
- **Offline evaluation:** a CLI batch job computes evaluations, and the API only reads them. Forecasts use the selected configuration, or the holidays-only default until a product is evaluated (ADR-0006).
- **Persistence:** forecast runs always cover 90 days and store cumulative sample paths, so reads never train. Evaluation runs carry the selected configuration. Stale runs are flagged (ADR-0010). **BREAKING:**
  - `POST /api/forecast` and `GET /api/forecast/<id>` response shapes gain run metadata;
  - `forecast_days` is limited to 1–90;
  - `GET /api/accuracy/<id>` returns a richer structure;
  - there is no `POST /api/evaluate`.
- **Reproducible setup:** a seeded synthetic dataset shaped like Favorita (known promo effect, useless oil, holiday types, closures) is the default for `docker compose up`, and Favorita is loaded through an opt-in profile (ADR-0011).
- **Engineering hardening:** connection pooling, batched inserts, input validation, generic error responses, and pytest in three tiers (`unit`/`db`/`slow`) with CI running real Prophet on reduced synthetic data (ADR-0013).
- **Frontend platform:** replace the deprecated Create React App with a fresh **Vite + React + TypeScript** app using **Tailwind CSS v4** and **shadcn/ui** components. Charts use shadcn's Recharts-based Chart component, and tests move to Vitest. This also removes the `overrides` patches for vulnerable `react-scripts` dependencies (ADR-0014).
- **UI:** shadcn-based components for controls, forecast chart (with seasonal-naive reference line), accuracy panel and inventory panel. Shows the as-of date, verdict and risk badges, stale/not-evaluated alerts, skeleton loading states and error states.

## Capabilities

### New Capabilities
- `forecast-data`: Data preparation: daily aggregation, units, training window, closure days, holiday frame mapping, regressor knowledge policy, planned promotions, synthetic dataset.
- `rolling-cv-evaluation`: Rolling-origin CV with production future frames, selection/test folds, baselines, bucketed metrics, regressor ablation, verdicts, calibration, offline evaluation job.
- `inventory-recommendations`: Reorder point, safety stock, stock-out probability and risk from forecast sample paths.
- `forecast-persistence`: Forecast and evaluation runs, staleness, API response metadata, validation and error handling, reproducible environment and tests.

### Modified Capabilities
<!-- openspec/specs/ is empty; no existing specs to modify. -->

## Impact

- **Code:**
  - `backend/forecaster.py` is replaced by `data.py`, `holidays.py`, `model.py`, `evaluation.py`, `inventory.py` and an `evaluate` CLI.
  - Also changed: `backend/app.py`, `backend/database.py`, `backend/import_kaggle_store_sales.py`, `backend/generate_sample_data.py` (rewritten) and `database/schema.sql`.
  - `frontend/` is re-scaffolded on Vite + TypeScript, with components in `src/components/` and shadcn primitives in `src/components/ui/`.
- **Schema:**
  - new tables `forecast_runs`, `forecast_run_samples`, `evaluation_runs`, `evaluation_metrics`, `evaluation_service_level` and `planned_promotions`;
  - `forecasts.run_id`;
  - `sales_data.quantity_sold` → `NUMERIC(12,3)`.
- **API:** `/api/forecast` and `/api/accuracy/<id>` changed; new `GET /api/inventory/<id>`; no evaluation write endpoint.
- **Dependencies:**
  - Backend: pytest. Prophet stays, with no Stan compile step.
  - Frontend: Vite, TypeScript, Tailwind CSS v4, shadcn/ui (plus its Radix primitives), Vitest, `@testing-library/react`. Removed: `react-scripts` and `axios`.
  - Docker and GitHub Actions config.
- **Constraints:** Prophet stays the forecasting model; rolling cross-validation stays the evaluation method.
- **Data:** a Favorita re-import is required (fractional quantities, planned promotions from `test.csv`).
