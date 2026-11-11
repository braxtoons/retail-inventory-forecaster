## Context

The backend has one class (`InventoryForecaster`) that fetches data, trains Prophet with oil/holiday/promo regressors, saves forecasts, and computes accuracy. Problems:
- Accuracy training omits the regressors, uses one 80/20 split, and has no baseline.
- Future regressor values are fabricated (last oil price, zero promos).
- The sales query LEFT JOINs national holidays, which double-counts sales on six dates with two holiday rows, and it treats transferred holidays and make-up work days as holidays.
- Weighed families are truncated to integers on import.
- Every request retrains Prophet, opens fresh DB connections, and inserts rows one at a time.
- No tests or containerization exist.

Hard constraints from the owner: **Prophet remains the forecasting model** and **rolling cross-validation remains the evaluation method**.

Vocabulary is defined in [`CONTEXT.md`](../../../CONTEXT.md). Each decision below is summarised; the linked ADR in [`docs/adr/`](../../../docs/adr/) has the full rationale and rejected alternatives.

## Goals / Non-Goals

**Goals:**
- Trustworthy, reproducible accuracy numbers: rolling CV that builds each fold exactly as production would, with held-out test folds and honest baselines.
- Evidence-based regressor selection.
- Turn forecasts into calibrated inventory recommendations for a single DC.
- Fast reads via persisted runs; test coverage including ground-truth checks; one-command setup.

**Non-Goals:**
- Replacing Prophet (baselines are naive only).
- Auth, multi-tenancy, or a job queue (evaluation is an offline CLI).
- Per-store or per-SKU forecasting and inventory.
- Modelling stock already on order, or fill rate.
- Editing planned promotions (seed-only).
- Horizons beyond 90 days.

## Decisions

**1. Domain framing (ADR-0001).** Product = family aggregated across stores. Inventory = stock at one notional DC. `quantity_sold` becomes `NUMERIC(12,3)`, and the importer stops truncating.

**2. Module split.**
- `data.py`: history queries, with no holiday join.
- `holidays.py`: builds the holidays frame.
- `model.py`: `build_model(config)` and `build_future_frame(history, horizon, as_of)`, shared by production and CV.
- `evaluation.py`: folds, baselines, metrics, ablation, verdicts, calibration.
- `inventory.py`: pure functions over sample paths.
- `evaluate.py`: the CLI.

*Why:* one model factory and one future-frame builder guarantee CV scores what ships.

**3. Rolling CV scores production's assumptions (ADR-0002).**
- A custom loop gets cutoffs from `prophet.diagnostics.generate_cutoffs`. Each fold fits `build_model` and predicts on `build_future_frame(as_of=cutoff)`.
- Regressor knowledge policy:
  - holidays: calendar (known in advance);
  - promotions: planned promotions, 0 where none (actual history stands in for "planned" in CV);
  - oil: last value carried forward.
- `prophet.diagnostics.cross_validation` is not used, because it feeds actual future regressor values.

**4. Data window and cleaning (ADR-0003, ADR-0011).** For Favorita, `TRAINING_START_DATE = 2014-04-01` for every configuration, because promotions are unrecorded before then. For synthetic data it is `None`. Closure days are absent rows, not zeros.

**5. Holiday frame (ADR-0004).** National rows only:
- `Holiday` with `transferred=True` is dropped;
- a `Transfer` row takes the original holiday's name;
- `Additional` rows and recurring events are named by their description;
- `Bridge` → `bridge`, `Work Day` → `work_day`;
- the 2016 earthquake and the 2014 World Cup are one-off shock events;
- regional and local holidays are ignored.

**6. Horizon and fold layout (ADR-0005).** `MAX_FORECAST_DAYS = 90`. Evaluation always runs at horizon 90 with `initial = 365` and `period = 60`. Metrics are reported per bucket (1–7, 8–30, 31–90) and overall. The as-of date is the last history date.

**7. Selection vs. test folds and ablation (ADR-0007).**
- The last 3 cutoffs are test folds.
- Earlier cutoffs whose windows end by the first test cutoff are selection folds; any fold overlapping the test period is dropped.
- Ablation arms: none, holidays, holidays+promo, holidays+oil, holidays+promo+oil.
- Greedy from holidays-only: a change is accepted only if it improves overall selection WAPE by ≥ 2% relative and wins in ≥ 2/3 of selection folds.
- Headline metrics come from test folds only.
- Minimum history: 3 test + 3 selection folds.

**8. Baselines, metrics, verdicts (ADR-0012).**
- Naive and seasonal-naive (7-day), on identical folds. A missing lag falls back to the latest prior observation.
- Metrics: MAE, RMSE, WAPE (headline), zero-safe MAPE with an excluded count, and 95% interval coverage.
- Skill = `1 − WAPE_prophet / WAPE_snaive`.
- Verdict per bucket: `beats` if skill ≥ +5% and ≥ 2/3 test-fold wins; `worse` if skill ≤ −5% and ≥ 2/3 test-fold losses; else `comparable`.

**9. Inventory (ADR-0008, ADR-0009).**
- Service level = cycle service level α (default 0.95; lead time default 7, range 1–90).
- `predictive_samples` gives 1000 seeded paths. Daily values are clipped at 0, then accumulated.
- ROP = α-quantile of the day-L cumulative demand. Safety stock = ROP − mean.
- Stock-out probability P = share of paths whose day-L cumulative demand exceeds on-hand.
- Risk: `ok` if P ≤ 1−α, `elevated` if P < 0.5, else `high`. `reorder_now` = on-hand ≤ ROP.
- Stock-out dates come from the median path and the 90th-percentile path over the full horizon.
- Inventory position = on-hand only.
- Calibration: achieved cycle service level on test folds.

**10. Offline evaluation (ADR-0006).** `python -m evaluate --all | --product <id>` with process parallelism. The API is read-only for evaluation, and `GET /api/accuracy/<id>` returns 404 when a product hasn't been evaluated. Forecasts use the latest evaluation's selected configuration, otherwise the holidays-only default, and report `config_source`.

**11. Persistence (ADR-0010).**
- A forecast run always covers 90 days. It stores config, `config_source`, seed, as-of date, `promo_known_through`, data fingerprint, daily rows and cumulative sample paths (`REAL[][]`).
- Writes are atomic, and only the latest 5 runs per product are kept.
- Evaluation runs store CV params, metrics rows, calibration rows and `selected_config`. There is no separate config table.
- Runs whose config or fingerprint mismatch are served with `stale: true`. Reads never train.

**12. Planned promotions (ADR-0002).** The `planned_promotions` table is seeded from Kaggle `test.csv` (or the synthetic generator). There is no write API. Responses include `promo_known_through`.

**13. Default dataset (ADR-0011).**
- A seeded Favorita-shaped synthetic generator is the Compose default. It has a known promo effect, a no-effect oil random walk, ADR-0004 holiday types, closures, a fractional product, and a fixed as-of date.
- Favorita loads via `--profile kaggle`.
- Ground-truth tests rely on the synthetic data.

**14. Infrastructure and tests (ADR-0013).**
- `ThreadedConnectionPool` behind a context manager; `execute_values` for inserts.
- Small validation helpers; generic 500s with server-side logging.
- pytest tiers `unit` / `db` / `slow`, with API tests behind a fake model.
- GitHub Actions runs all tiers (slow tier on a reduced synthetic config), frontend component tests and `npm run build`.
- `python:3.11-slim` backend image.

**15. Frontend platform (ADR-0014).**
- Fresh Vite + React + TypeScript scaffold; components are ported, not migrated in place.
- Tailwind CSS v4 via `@tailwindcss/vite`; shadcn/ui with the `@/` alias.
- Charts via the shadcn Chart component (Recharts).
- Typed `fetch` client replaces axios.
- Dev server on port 3000 with `server.proxy` for `/api`; `npm start` kept as an alias.
- Vitest + Testing Library.
- Production image: `vite build` served by nginx.
- *Why:* CRA is deprecated and cannot host Tailwind or aliases without CRACO or eject, and the UI is being rewritten anyway.

## Risks / Trade-offs

- **[Only 3 test folds make the headline metrics noisy]** → Show per-fold values; verdicts require a majority of folds and a ±5% threshold.
- **[Prophet intervals are often too narrow, so ROP understates risk]** → The calibration check reports achieved vs. target service level honestly. Empirical residual quantiles are the documented refinement.
- **[The custom CV loop is ours to get right]** → Unit test for future-frame parity; ground-truth slow tests on synthetic data.
- **[DC-level pooling understates per-store safety stock]** → Stated in the README and UI copy (ADR-0001).
- **[Promo is unknown beyond `promo_known_through`, so forecasts under-predict promo days]** → Surfaced in responses and the UI, not corrected.
- **[Evaluation takes about 1–2 min per product]** → Offline CLI with process parallelism; results cached.
- **[Sample path storage of about 360 KB per run]** → Retention of 5 runs per product (~60 MB worst case for Favorita).
- **[Breaking API shapes]** → Frontend updated in the same change; documented in the README.
- **[CI time from the slow tier]** → Reduced config; can move to nightly without redesign.
- **[Frontend rewrite and API changes land together]** → Typed API client in one module; component tests against mocked responses for every state.
- **[shadcn components are vendored into the repo]** → Treated as owned code; updated deliberately via the shadcn CLI, not automatically.

## Migration Plan

1. Schema migration (idempotent):
   - create `forecast_runs`, `forecast_run_samples`, `evaluation_runs`, `evaluation_metrics`, `evaluation_service_level`, `planned_promotions` (`IF NOT EXISTS`);
   - `ALTER TABLE forecasts ADD COLUMN IF NOT EXISTS run_id`;
   - `ALTER TABLE sales_data ALTER COLUMN quantity_sold TYPE NUMERIC(12,3)`, which widens the type and is safe for existing integers.
2. Re-import data (Favorita: fractional quantities and planned promotions; or synthetic). Existing `forecasts` rows without `run_id` are deleted.
3. Run `python -m evaluate --all`.
4. Deploy the backend and frontend together.
5. Rollback: revert the commit. The new tables are ignored by the old code, and the `NUMERIC` column is readable by the old code.

## Open Questions

None outstanding. Earlier questions are resolved: default lead time and service level are 7 days and 95% (ADR-0008); the documented dataset is Favorita, with synthetic data as the out-of-the-box default (ADR-0003, ADR-0011).
