## 1. Infrastructure and Test Scaffolding

- [x] 1.1 Add pytest and test dependencies to `backend/requirements.txt`; create `backend/tests/` with `unit`/`db`/`slow` markers and a Postgres test fixture (ADR-0013)
- [x] 1.2 Replace per-call connections in `backend/database.py` with a `ThreadedConnectionPool` and a context-manager helper
- [x] 1.3 Add an idempotent migration to `database/schema.sql`:
  - create `forecast_runs`, `forecast_run_samples`, `evaluation_runs`, `evaluation_metrics`, `evaluation_service_level`, `planned_promotions`;
  - add `forecasts.run_id`;
  - change `sales_data.quantity_sold` to `NUMERIC(12,3)` (ADR-0001, ADR-0010)
- [x] 1.4 Add a config module entry for `TRAINING_START_DATE`, `MAX_FORECAST_DAYS`, CV `initial`/`period`, ablation and verdict thresholds, and `uncertainty_samples`
- [x] 1.5 Add `docker-compose.yml` and Dockerfiles:
  - backend image on `python:3.11-slim`;
  - frontend image runs `vite build` and serves `dist/` with nginx, proxying `/api`;
  - schema applied on DB start;
  - one-off `seed` and `evaluate` services;
  - `kaggle` profile mounting `data/store-sales`
- [x] 1.6 Add a GitHub Actions workflow with a Postgres service, running all pytest tiers (reduced slow config), frontend Vitest suite and type check, and `npm run build`

## 2. Data Preparation (`forecast-data`)

- [x] 2.1 Create `backend/data.py`:
  - daily history query per product with no holiday join;
  - honour the training window;
  - closure days absent;
  - replace deprecated `fillna(method=...)`;
  - shared `data_fingerprint` helper
- [x] 2.2 Create `backend/holiday_frame.py` (not `holidays.py`: that name would shadow the PyPI `holidays` package Prophet imports) building the Prophet holidays frame per the ADR-0004 mapping, including the `earthquake_2016` and `world_cup_2014` shock events
- [x] 2.3 Update `import_kaggle_store_sales.py`: keep fractional quantities, batch inserts, seed `planned_promotions` from `test.csv`
- [x] 2.4 Rewrite `generate_sample_data.py` as the seeded, Favorita-shaped synthetic generator (ADR-0011) and document its parameters
- [x] 2.5 Regression test (`db`): per-date `y` equals the raw per-date sales sum on dates with multiple national holiday rows (e.g. 2016-05-01, 2016-05-08, 2014-12-26)
- [x] 2.6 Unit-test the holiday mapping (transferred original dropped, transfer renamed, bridge/work day, shock events, regional ignored) and generator determinism

## 3. Model and Production Forecast

- [x] 3.1 Create `backend/model.py` with `build_model(config)` (holidays via `holidays=`, regressors per config) and `build_future_frame(history, horizon, as_of)` applying the regressor knowledge policy (ADR-0002)
- [x] 3.2 Implement forecast generation:
  - selected configuration, or the holidays-only default;
  - always 90 days;
  - seeded `predictive_samples` (1000 paths, clipped and cumulated);
  - atomic run write with `execute_values`;
  - prune to 5 runs (ADR-0010)
- [x] 3.3 Implement staleness detection (config or fingerprint mismatch)
- [x] 3.4 Unit-test the model factory (regressors and holidays registered) and future-frame parity between production and a CV cutoff

## 4. Rolling Cross-Validation Evaluation (`rolling-cv-evaluation`)

- [x] 4.1 Create `backend/evaluation.py`: cutoffs via `generate_cutoffs` (initial 365, horizon 90, period 60); selection/test fold split with overlap dropping; minimum-history check (ADR-0005, ADR-0007)
- [x] 4.2 Implement the custom rolling loop using `build_model` and `build_future_frame(as_of=cutoff)`
- [x] 4.3 Implement naive and seasonal-naive baselines on identical cutoffs, with missing-lag fallback
- [x] 4.4 Implement metrics per fold and horizon bucket: MAE, RMSE, WAPE, zero-safe MAPE with excluded count, coverage, skill
- [x] 4.5 Implement the greedy ablation (≥ 2% relative gain and ≥ 2/3 fold wins) and verdicts (±5%, ≥ 2/3 folds) (ADR-0007, ADR-0012)
- [x] 4.6 Implement service-level calibration on test folds (ADR-0008)
- [x] 4.7 Create the `evaluate` CLI (`--all` / `--product`) with process parallelism, persisting evaluation runs and the selected config; report skipped products (ADR-0006)
- [x] 4.8 Unit-test metrics on hand-computed examples, zero-actual handling, fold generation and split, the ablation rule on made-up scores, and verdict thresholds
- [x] 4.9 Slow tests on synthetic data: ablation selects promo and excludes oil; achieved service level is near target
- [x] 4.10 Run the evaluation on Favorita for all products and record the findings in the README: verdict counts per bucket, pooled achieved service level, which regressors were selected

## 5. Inventory Recommendations (`inventory-recommendations`)

- [x] 5.1 Create `backend/inventory.py` with pure functions over cumulative sample paths: ROP, safety stock, stock-out probability, risk level, `reorder_now`, projected and earliest stock-out dates (ADR-0008, ADR-0009)
- [x] 5.2 Add parameter validation: lead time 1–90, α in (0.5, 0.999), on-hand ≥ 0
- [x] 5.3 Unit-test:
  - monotonicity in α and in on-hand;
  - on-hand = ROP gives `ok`;
  - on-hand = 0 gives `high` on day 1;
  - `beyond_horizon`;
  - lead-time scaling

## 6. API

- [x] 6.1 Add request validation helpers and generic error responses with server-side logging
- [x] 6.2 `POST /api/forecast`: generate and persist a run, return it with metadata. `GET /api/forecast/<id>`: serve the latest run trimmed to `forecast_days` (1–90), with `stale`, `config_source`, `as_of_date`, `promo_known_through` and the seasonal-naive reference series
- [x] 6.3 `GET /api/accuracy/<id>`: latest evaluation (test-fold metrics, skill and verdict per bucket, per-fold values, labelled ablation table, achieved service level); 404 if not evaluated
- [x] 6.4 `GET /api/inventory/<id>`: `lead_time`, `service_level` and `on_hand` params; recommendation, risk, dates, assumptions, 1–7 verdict; 404 if no forecast run
- [x] 6.5 Integration-test all endpoints (`db` tier) with a fake model behind the `build_model` interface

## 7. Frontend

- [x] 7.0a Scaffold a fresh Vite + React + TypeScript app in `frontend/`:
  - remove `react-scripts`, the `overrides` block, `eslintConfig`, `browserslist` and `axios`;
  - dev server on port 3000 with `server.proxy` for `/api`;
  - keep `npm start` as an alias for `vite` (ADR-0014)
- [x] 7.0b Add Tailwind CSS v4 (`@tailwindcss/vite`) and initialise shadcn/ui (`components.json`, `@/` alias in `tsconfig` and `vite.config.ts`); add the components listed in ADR-0014, including Chart
- [x] 7.0c Add Vitest + jsdom + `@testing-library/react`; create the typed API client and response types in `src/api/`
- [x] 7.1 Build components with shadcn primitives (controls, forecast chart via shadcn Chart/Recharts, accuracy panel, inventory panel), porting behaviour from the old `App.js`; delete `App.css`
- [x] 7.2 Forecast chart: seasonal-naive reference line; show the as-of date prominently; stale banner with Regenerate; `config_source` indicator; note on promotions after `promo_known_through`
- [x] 7.3 Accuracy panel:
  - model vs. baselines per bucket;
  - verdict badges for the buckets covered by the requested horizon;
  - per-fold chart;
  - ablation table labelled "selection folds";
  - achieved vs. target service level;
  - plain-language explanation;
  - not-evaluated empty state
- [x] 7.4 Inventory panel:
  - inputs for lead time, service level and on-hand;
  - outputs for ROP, safety stock, risk level, `reorder_now` and stock-out dates;
  - assumptions text;
  - warning when the 1–7 verdict is `worse`;
  - generate-first state
- [x] 7.5 Loading and error states; read cached forecasts on product selection
- [x] 7.6 Vitest component tests for the panels: loaded, not evaluated, error, stale, `worse` verdict

## 8. Documentation

- [x] 8.1 Update README, QUICKSTART, `setup.sh` and CLAUDE.md: architecture (Vite + TypeScript + shadcn frontend), synthetic default vs. Kaggle profile, evaluation methodology, API changes, Docker setup; link `CONTEXT.md` and `docs/adr/`
- [x] 8.2 Document the Favorita CV results and ablation findings, the DC-level pooling caveat, and which metrics the project can honestly claim
