# Domain Glossary

Shared vocabulary for the Retail Inventory Forecaster. Code, specs, API fields and UI copy should use these terms with these meanings.

## Core terms

**Product**
A product family from the source data (e.g. `BEVERAGES`, `PRODUCE`), aggregated across all stores. It is *not* an individual SKU and *not* a per-store item. One product = one forecast series. See [ADR-0001](docs/adr/0001-inventory-held-at-single-dc.md).

**Distribution Centre (DC)**
The single, notional stocking location that supplies the whole chain. All inventory quantities (on-hand, safety stock, reorder point) refer to stock of a product held at the DC. This is a modelling abstraction; the source data contains no DC or stock levels.

**Demand**
Units of a product sold per day across all stores. Used as the forecast target (`y`). Treated as demand even though it is really *sales*: stock-outs in the source data would censor true demand, and this is not corrected for.

**Unit of measure**
Most products are counted in whole units. Weighed families (MEATS, POULTRY, DELI, PRODUCE, PREPARED FOODS, FROZEN FOODS, SEAFOOD, BREAD/BAKERY, and partially GROCERY I) are measured in fractional quantities (e.g. kg) and must be stored and forecast as non-integer values, never truncated.

**On-hand**
Quantity of a product currently in stock at the DC. Supplied by the user; not stored in the database.

## Data

**Training window**
The span of history used for fitting and evaluation. For Favorita it starts 2014-04-01, because promotion data before then is unrecorded. See [ADR-0003](docs/adr/0003-favorita-training-window-and-cleaning.md).

**Closure day**
A date on which stores did not trade (e.g. Dec 25). Treated as *missing*, never as zero demand.

**Shock event**
A one-off disruption (e.g. the 2016 Manabí earthquake) modelled as its own non-recurring holiday so its effect is not repeated in future forecasts.

## Inventory

**Lead time (L)**
Days between placing a replenishment order with the DC's supplier and receiving it. Default 7, range 1–90.

**Lead-time demand**
Total demand over days 1..L after the as-of date. A distribution, not a number: derived from Prophet sample paths. See [ADR-0008](docs/adr/0008-lead-time-demand-from-sample-paths.md).

**Service level (cycle service level, α)**
The target probability of *not* running out of stock during one lead time: P(lead-time demand ≤ reorder point). Default 0.95. Not the same as *fill rate* (share of demand served), which this project does not compute.

**Reorder point (ROP)**
The α-quantile of lead-time demand. Place an order when stock falls to this level.

**Safety stock**
Reorder point minus mean lead-time demand: the buffer held against forecast uncertainty.

**Stock-out probability**
Share of demand sample paths whose cumulative demand over the lead time exceeds on-hand.

**Risk level**
`ok` (P ≤ 1 − α), `elevated` (1 − α < P < 0.5), `high` (P ≥ 0.5). Tied to the service level so it never contradicts the reorder point. See [ADR-0009](docs/adr/0009-stock-out-risk-levels.md).

**Reorder now**
On-hand ≤ reorder point.

**Projected stock-out date / earliest likely stock-out date**
First day the median (resp. 90th-percentile) cumulative demand path exceeds on-hand, within the forecast horizon.

**Inventory position**
Stock available to meet demand. In this project it equals on-hand; stock already on order is out of scope.

**Achieved service level**
The share of CV test folds in which actual lead-time demand was ≤ the forecast reorder point. Compared against α to show whether the forecast's uncertainty is calibrated.

## Persistence

**Forecast run**
One stored execution of the production forecast for a product: always the full 90-day horizon, with its configuration, seed, as-of date, daily forecasts and cumulative demand sample paths. The latest 5 per product are kept. See [ADR-0010](docs/adr/0010-forecast-and-evaluation-persistence.md).

**Evaluation run**
One stored execution of the evaluation job for a product: CV parameters, metrics per model/arm/fold/bucket, calibration hits, and the selected configuration.

**Data fingerprint**
A short hash of a product's history (row count plus max date) used to detect that stored runs predate a data re-import.

**Stale run**
A forecast run whose configuration or data fingerprint no longer matches the current ones. Served with `stale: true`; never regenerated automatically on read.

## Forecasting and evaluation

**Regressor**
An external signal fed to Prophet alongside history: holidays, promotions, oil price. Each regressor has a *knowledge policy* stating what production knows about its future values. See [ADR-0002](docs/adr/0002-cv-uses-production-regressor-assumptions.md).

**Known-in-advance regressor**
A regressor whose future values are genuinely available at forecast time: holidays (calendar) and planned promotions.

**Planned promotion**
A promotion count for a product on a future date, entered ahead of time. Absent entries mean 0. `promo_known_through` is the last date with planned-promotion data.

**Carried-forward regressor**
A regressor whose future is unknown and is filled with its last observed value (oil price).

**Model configuration**
The set of regressors (and holiday frame) a Prophet model is built with. Built only by `build_model(config)`.

**Ablation arm**
One model configuration scored by rolling CV during regressor ablation: none, holidays, holidays+promo, holidays+oil, holidays+promo+oil.

**Selected configuration**
The configuration the ablation chose for a product, persisted and used by production forecasts.

**Default configuration**
Holidays only. Used for a product that has not been evaluated yet. Forecast responses report `config_source: "selected" | "default"`. See [ADR-0006](docs/adr/0006-offline-batch-evaluation.md).

**Evaluation**
The offline batch job (CLI) that runs rolling CV, baselines and ablation for products and stores the results. The API only reads evaluation results.

**Cutoff**
The "as of" date of one evaluation fold. The model sees only data up to and including the cutoff, then forecasts the following horizon.

**Fold**
One cutoff plus its forecast horizon and the actuals it is scored against.

**As-of date**
The last date in a product's history. Forecasts begin the day after it, and on-hand stock is interpreted as of this date. For Favorita this is 2017-08-15, regardless of today's wall-clock date. See [ADR-0005](docs/adr/0005-forecast-horizon-and-evaluation-buckets.md).

**Forecast horizon**
Number of days forecast past the as-of date: 1 to 90.

**Horizon bucket**
A band of horizon days that accuracy is reported for: 1–7, 8–30, 31–90. Accuracy for a day-3 forecast and a day-80 forecast are different numbers and must not be merged into one headline.

**Rolling-origin cross-validation (rolling CV)**
Evaluation over several folds with successive cutoffs. Each fold must build its future frame exactly as production would on the cutoff date.

**Selection folds**
Earlier CV folds used only to choose the model configuration in the ablation. Scores on them are optimistic for the chosen arm and are labelled as such.

**Test folds**
The 3 most recent CV folds, never used for selection. All headline accuracy numbers come from them. See [ADR-0007](docs/adr/0007-ablation-selection-with-held-out-test-folds.md).

**Baseline**
A simple reference forecast scored on the same folds: *naive* (repeat the last observed value) and *seasonal-naive* (repeat the value from 7 days earlier, i.e. the last observed week).

**Skill (vs. seasonal-naive)**
`1 − WAPE_prophet / WAPE_seasonal_naive`. Positive means Prophet beats the baseline; zero or negative means it does not.

**Verdict**
Per product and horizon bucket: `beats`, `comparable` or `worse` vs. seasonal-naive, requiring both a skill threshold (±5%) and a majority of test folds. See [ADR-0012](docs/adr/0012-baseline-verdicts.md).

**WAPE**
Weighted absolute percentage error: `Σ|actual − forecast| / Σ actual`. The headline accuracy metric, because it stays defined when some days have zero sales.
