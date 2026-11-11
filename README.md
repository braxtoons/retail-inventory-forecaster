# Retail Inventory Forecaster

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=black)
![TypeScript](https://img.shields.io/badge/TypeScript-Vite-3178C6?style=flat&logo=typescript&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=flat&logo=flask&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-12+-4169E1?style=flat&logo=postgresql&logoColor=white)
![Prophet](https://img.shields.io/badge/Prophet-1.1.5-FF6F00?style=flat)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

A full-stack application that forecasts retail demand with Prophet, **measures how good those forecasts really are** (rolling cross-validation against naive baselines, on held-out folds), and turns them into **reorder recommendations** with explicit service-level semantics.

Domain vocabulary lives in [`CONTEXT.md`](CONTEXT.md); every design decision is recorded as an ADR in [`docs/adr/`](docs/adr/).

## Tech stack

- **Frontend**: React + TypeScript on Vite, Tailwind CSS v4, shadcn/ui components, Recharts (via shadcn Chart), Vitest
- **Backend**: Python + Flask, psycopg2 connection pool
- **Database**: PostgreSQL
- **Model**: Prophet (the forecasting model); naive and seasonal-naive are baselines only
- **Data processing**: Pandas

## What it does

- Forecasts up to **90 days** per product with a 95% prediction interval, using the product's *selected* regressor configuration (holidays, promotions, oil price) once evaluated, or a holidays-only default before that.
- **Rolling-origin cross-validation** that builds every fold's future frame exactly as production would. Holidays come from the calendar, promotions from *planned* promotions, oil is carried forward. Nothing in a fold sees the future.
- **Honest model selection**: a regressor ablation on *selection folds*, with all headline numbers taken from 3 held-out *test folds*.
- **Baselines and verdicts**: Prophet vs. naive and seasonal-naive per horizon bucket (days 1-7, 8-30, 31-90), summarised as `beats` / `comparable` / `worse`.
- **Inventory recommendations**: reorder point, safety stock, stock-out probability, risk level, `reorder now` and projected stock-out dates, from Prophet's simulated demand paths.
- Stored **forecast runs** (reads never train) with stale-run detection.

### Domain framing

- A **product** is a product family (e.g. `BEVERAGES`) aggregated across all stores, not a SKU ([ADR-0001](docs/adr/0001-inventory-held-at-single-dc.md)).
- Inventory quantities (on-hand, reorder point, safety stock) refer to one notional **distribution centre**. Pooling every store into one DC understates the safety stock a single store would need, because per-store demand is much more variable than the pooled total.
- Weighed families (PRODUCE, MEATS, ...) keep **fractional quantities**; nothing is truncated to integers.

## Prerequisites

- Python 3.11+ (developed on 3.12)
- Node.js 20.19+ or 22+ (Vite 8)
- PostgreSQL 12+ (a database you can create tables in)
- Optional: Docker, for `docker compose up` (the Compose setup has not yet been run end to end)

## Quick start

See [`QUICKSTART.md`](QUICKSTART.md) for details.

```bash
docker compose up --build        # Postgres + backend + frontend, seeded synthetic data, evaluated
# frontend http://localhost:3000, API http://localhost:5000
```

Or locally (the database must exist first; the schema is applied by `python database.py` below):

```bash
createdb retail_forecaster                   # skip if it exists; without CREATEDB see the note below
cd backend && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
cp .env.example .env                         # set DATABASE_URL
python database.py                           # applies database/schema.sql (idempotent; also migrates an older DB)
python generate_sample_data.py               # seeded synthetic dataset
python -m evaluate --all                     # offline evaluation
python app.py                                # API on :5000
cd ../frontend && npm install && npm start   # UI on :3000 (Vite proxies /api)
```

> **`createdb: permission denied to create database`?** Your Postgres role lacks `CREATEDB`. Either have a superuser create the database for you, e.g. `sudo -u postgres createdb -O "$USER" retail_forecaster`, or reuse an existing database you own. Nothing else needs the privilege: the app creates only tables, and the DB tests use a throwaway *schema* inside `DATABASE_URL`'s database.

### Upgrading an existing database

If you ran an earlier version of this project, run `python database.py` first. It adds the new tables, widens `sales_data.quantity_sold` to `NUMERIC(12,3)` and **deletes old forecast rows** that have no run. Then reload data (`python generate_sample_data.py`, which replaces the old sample data) and run `python -m evaluate --all`.

## Using the UI

1. Pick a product. Stored accuracy and the latest forecast load immediately; selecting a product never trains a model.
2. Click **Generate forecast** to train once and store a new 90-day run. The **forecast horizon** slider (1-90 days) only changes how much of the stored run is displayed.
3. **Chart**: actual sales, forecast (dashed), 95% interval, and a faint seasonal-naive line (last week repeated). The *as-of date* and the configuration in use (`Selected` after evaluation, `Default` before) are shown. A banner offers **Regenerate** if the run is stale; a note says promotions after `promo_known_through` are assumed zero.
4. **Forecast accuracy**: per horizon range, Prophet vs. naive vs. seasonal-naive (WAPE, MAE, RMSE, MAPE, coverage), a verdict badge, per-fold chart, the ablation table (labelled *selection folds*) and achieved vs. target service level. Products not yet evaluated show a "Not evaluated yet" state.
5. **Inventory recommendation**: set lead time, service level and on-hand stock to see reorder point, safety stock, risk level, *reorder now* and stock-out dates. A warning appears if the 1-7 day verdict is `worse`.

## Configuration

Set in `backend/.env` (all optional except `DATABASE_URL`):

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | local Postgres | Connection string |
| `FLASK_PORT` | 5000 | API port |
| `TRAINING_START_DATE` | `2014-04-01` | First date used for training and evaluation; empty = all history |
| `MAX_FORECAST_DAYS` | 90 | Maximum horizon |
| `CV_INITIAL_DAYS` / `CV_PERIOD_DAYS` | 365 / 60 | Rolling-CV layout |
| `UNCERTAINTY_SAMPLES` | 1000 | Prophet sample paths per forecast run |
| `ABLATION_MIN_REL_GAIN`, `ABLATION_MIN_FOLD_WIN_SHARE` | 0.02, 0.667 | Regressor-selection thresholds |
| `VERDICT_SKILL_THRESHOLD`, `VERDICT_MIN_FOLD_SHARE` | 0.05, 0.667 | Verdict thresholds |

## Database schema

- Source data: `products`, `sales_data` (daily per product, `quantity_sold NUMERIC(12,3)`), `oil_prices`, `holidays`, `planned_promotions` (seed-only).
- Forecasts: `forecast_runs` (config, source, seed, as-of date, `promo_known_through`, data fingerprint), `forecasts` (daily rows per run), `forecast_run_samples` (1000 x 90 cumulative paths). The latest 5 runs per product are kept.
- Evaluation: `evaluation_runs` (CV params, selected configuration), `evaluation_metrics` (per model/arm/fold/bucket), `evaluation_service_level`.

## Project layout

```
backend/    app.py  data.py  holiday_frame.py  model.py  forecast_runs.py  inventory.py
            evaluation.py  evaluation_store.py  evaluate.py  generate_sample_data.py
            import_kaggle_store_sales.py  config.py  database.py  tests/
frontend/   src/App.tsx  src/api/  src/components/ (+ ui/ shadcn)  src/test/
database/   schema.sql          docs/adr/  decisions          CONTEXT.md  glossary
openspec/   change proposal, design, specs, tasks
```

## Datasets

**Default: seeded synthetic data** ([ADR-0011](docs/adr/0011-seeded-synthetic-dataset-as-default.md)). Shaped like Favorita, deterministic for a seed, with known ground truth that the tests assert:

| Parameter (`generate_sample_data.py`) | Default | Meaning |
|---|---|---|
| `SEED` | 7 | Same seed gives identical tables |
| `AS_OF` | 2024-12-31 | Last history date |
| `YEARS` | 3 | History length |
| `PLANNED_DAYS` | 30 | Planned-promotion window after the as-of date |

4 products (one weighed, fractional), weekly and yearly seasonality, trend, every holiday type, a transferred holiday, a bridge and a work day, a one-off shock event, Dec 25 closures, promotions with a known positive effect, and an **oil price random walk that has no effect on demand**.

**Optional: Kaggle Favorita "Store Sales"** ([ADR-0003](docs/adr/0003-favorita-training-window-and-cleaning.md)); see [`KAGGLE_IMPORT_INSTRUCTIONS.md`](KAGGLE_IMPORT_INSTRUCTIONS.md):

```bash
cd backend && TRAINING_START_DATE=2014-04-01 python import_kaggle_store_sales.py --data-dir ../data/store-sales
# or: TRAINING_START_DATE=2014-04-01 docker compose --profile kaggle up --build
```

Favorita training starts on **2014-04-01** because promotion data is unrecorded before then. That is why the history looks shorter than the raw files (about 3.4 of 4.6 years), not a bug. The 2016 earthquake and 2014 World Cup are modelled as one-off shock events so their effect is not projected onto future dates. Closure days (Dec 25) are *missing* observations, never zero demand. Planned promotions are seeded from Kaggle's `test.csv` (2017-08-16 to 2017-08-31); beyond `promo_known_through` the forecast assumes no promotions.

## Evaluation methodology

Run offline: `python -m evaluate --all` (or `--product <id>`), parallel across products. The API only reads results ([ADR-0006](docs/adr/0006-offline-batch-evaluation.md)).

- **Folds** ([ADR-0005](docs/adr/0005-forecast-horizon-and-evaluation-buckets.md), [ADR-0007](docs/adr/0007-ablation-selection-with-held-out-test-folds.md)): cutoffs from `prophet.diagnostics.generate_cutoffs` (initial 365 d, horizon 90 d, period 60 d). The **last 3 cutoffs are test folds**; earlier cutoffs whose window ends before the first test cutoff are **selection folds**; overlapping folds are dropped. A product needs about 815 days of history, else it is skipped and reported.
- **Custom loop, not `cross_validation`**: the stock function feeds *actual* future regressor values to the model, which production never has. Each fold here fits `build_model(config)` and predicts on `build_future_frame(as_of=cutoff)`, the same two functions production uses ([ADR-0002](docs/adr/0002-cv-uses-production-regressor-assumptions.md)). Actual historical promotions stand in for "planned" promotions inside folds, because promotions are planned ahead in this domain.
- **Ablation** (selection folds only): arms `none`, `holidays`, `holidays+promo`, `holidays+oil`, `holidays+promo+oil`. Greedy from holidays-only; a change is accepted only if it lowers pooled WAPE by at least 2% relative **and** wins in at least 2/3 of folds.
- **Metrics** per horizon bucket (1-7, 8-30, 31-90, overall): MAE, RMSE, **WAPE** (headline: total absolute error / total actuals, defined even with zero-sales days), zero-safe MAPE (with excluded count) and 95% interval coverage.
- **Baselines** on identical folds: *naive* (last value) and *seasonal-naive* (the last observed week repeated).
- **Skill** = `1 - WAPE_prophet / WAPE_seasonal_naive`. **Verdict** ([ADR-0012](docs/adr/0012-baseline-verdicts.md)): `beats` if skill >= +5% and Prophet wins >= 2/3 test folds; `worse` if skill <= -5% and loses >= 2/3; otherwise `comparable`.
- **Calibration** ([ADR-0008](docs/adr/0008-lead-time-demand-from-sample-paths.md)): on each test fold, was actual 7-day demand at or below the forecast 95% reorder point? The achieved service level is reported next to the 95% target.

## Inventory recommendations

From the latest forecast run's 1000 stored, seeded sample paths (daily demand clipped at 0, accumulated):

- **Service level** is the *cycle service level* alpha: the probability of not stocking out during one lead time. It is not fill rate.
- **Reorder point** = alpha-quantile of cumulative demand at day L. **Safety stock** = reorder point - mean lead-time demand.
- **Stock-out probability** P = share of paths whose lead-time demand exceeds on-hand. **Risk**: `ok` if P <= 1-alpha, `elevated` if P < 0.5, else `high` ([ADR-0009](docs/adr/0009-stock-out-risk-levels.md)). **Reorder now** = on-hand <= reorder point.
- **Stock-out dates**: first day the median (and the 90th-percentile) cumulative path exceeds on-hand, within the 90-day horizon.
- Inventory position equals on-hand: stock already on order is **not** modelled. Defaults: lead time 7 days (1-90), service level 0.95 (0.5-0.999).

## API

| Endpoint | Description |
|---|---|
| `GET /api/products` | Products |
| `GET /api/historical?product_id=&days_back=` | Daily history |
| `POST /api/forecast` `{product_id, forecast_days}` | Train once, store a 90-day run, return it trimmed to `forecast_days` (1-90, else 400) |
| `GET /api/forecast/:id?forecast_days=` | Latest stored run, never trains; 404 if none |
| `GET /api/accuracy/:id` | Stored evaluation; 404 naming the evaluate command if not evaluated |
| `GET /api/inventory/:id?lead_time=&service_level=&on_hand=` | Recommendation; 404 if no forecast run |
| `GET /api/health` | Health check |

Forecast responses include `run_id`, `created_at`, `as_of_date`, `config`, `config_source` (`selected`/`default`), `promo_known_through`, `stale` / `stale_reason`, and a per-day `seasonal_naive` reference. **Breaking changes** from the previous version: forecast response shapes gained run metadata; `forecast_days` is limited to 1-90; `/api/accuracy` returns a richer structure (no more bare `{mae, mape}`); there is no endpoint that triggers evaluation. Errors return `{"error": ...}`; unexpected failures return a generic 500 and are logged server-side.

## Architecture

```
Frontend (React + TS, Vite, shadcn/ui)        Backend (Flask)                         PostgreSQL
 Controls, ForecastChart,    --HTTP/JSON-->    app.py   routes + validation   --SQL--> sales_data, products, oil_prices,
 AccuracyPanel, InventoryPanel                 data.py / holiday_frame.py              holidays, planned_promotions,
                                               model.py (build_model,                  forecast_runs/forecasts/
                                                         build_future_frame)           forecast_run_samples,
                                               forecast_runs.py, inventory.py          evaluation_runs/metrics/
                                               evaluation*.py + evaluate.py (CLI)      service_level
```

## Testing

```bash
cd backend
pytest -m "not slow"     # fast loop: unit + db tiers, no Prophet fit
pytest                   # everything, including slow ground-truth tests
cd ../frontend && npm test && npm run typecheck && npm run build
```

- `unit`: metrics on hand-computed examples, fold generation and split, ablation rule, verdict thresholds, holiday mapping, future-frame parity between production and a CV cutoff, inventory maths.
- `db`: Postgres queries (including a regression test for the old holiday double-count), atomic run writes and pruning, staleness, API tests with a fake model behind `build_model`. They run inside a throwaway schema of `TEST_DATABASE_URL` (or `DATABASE_URL`), so they never touch real tables.
- `slow`: real Prophet on the synthetic dataset (reduced config) asserts that ablation selects promotions and rejects oil, and that the achieved service level is near target.
- CI (`.github/workflows/ci.yml`) runs all tiers with a Postgres service, plus frontend tests, type check and build.

## Favorita results (measured, not assumed)

Full run of `python -m evaluate --all` on Kaggle Favorita (loaded into a separate scratch schema, so it does not appear in the default UI data) (33 product families, training window 2014-04-01 to 2017-08-15, 3 test folds each, 99 in total). Nothing was skipped.

| Horizon bucket | Prophet beats seasonal-naive | Comparable | Worse |
|---|---|---|---|
| Days 1-7 | 10 | 9 | 14 |
| Days 8-30 | 10 | 9 | 14 |
| Days 31-90 | 8 | 8 | 17 |

- **Selected regressors**: holidays only 24, holidays+promo 5 (Eggs, Meats, Poultry, Produce, Seafood), holidays+oil 3 (Deli, Hardware, Magazines), none 1 (Celebration). Promotions earn their place for some food families but not for most; oil price was selected for 3 products and is likely noise there, since the ablation has only a handful of folds.
- **Achieved service level: 73.7%** (73 of 99 test folds) against a 95% target. Prophet's intervals are too narrow, so **reorder points computed from them understate risk**. Calibrating with empirical residual quantiles is the documented refinement and is not implemented.

### What this project can honestly claim

- Rolling-CV numbers come from held-out test folds, built exactly as production builds forecasts (no future regressor leakage), with regressors chosen on separate selection folds.
- On Favorita, Prophet is **not** generally better than repeating last week: it beats the baseline for roughly a third of families, and is worse for about 40-50%. Do not quote a single accuracy figure for the whole catalogue.
- Only 3 test folds per product, so per-product verdicts are noisy; the +/-5% and 2/3-fold rule reduces but does not remove that.
- Reorder points are **not** calibrated to the stated service level on this data (see above). Treat them as relative guidance, and read the "achieved service level" line next to them.
- Quantities are pooled to one notional distribution centre; per-store safety stock would be larger. Sales stand in for demand (stock-outs censor demand), and stock on order is ignored.
- Planned promotions beyond `promo_known_through` are unknown and assumed zero, so promotion days late in the horizon are under-predicted.


## Troubleshooting

- **Database connection**: check PostgreSQL is running and `DATABASE_URL` in `backend/.env`.
- **Accuracy panel says "Not evaluated yet"**: run `python -m evaluate --all`.
- **Forecast flagged out of date**: configuration or data changed since it was generated; click *Regenerate*.
- **Prophet install problems**: `pip install prophet` ships a precompiled Stan model; on Debian/Ubuntu you may also need `python3-dev`.
- **Ports**: backend `FLASK_PORT` in `.env`; frontend `npm start -- --port 3001`.
