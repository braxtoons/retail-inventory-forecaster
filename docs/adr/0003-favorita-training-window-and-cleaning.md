# ADR-0003: Keep the Favorita dataset; train from 2014-04-01, drop closure days, model the 2016 earthquake as its own event

- **Status:** Accepted
- **Date:** 2026-11-11
- **Change:** `improve-forecasting-evaluation-and-inventory`
- **Resolves:** design.md Open Question 2 (default dataset → Kaggle Favorita)

## Context

The Kaggle Store Sales (Favorita) dataset is the documented default. It covers 2013-01-01 → 2017-08-15 and fits the family-level single-DC framing (ADR-0001) and the promotions known in advance (ADR-0002, via `test.csv`). Inspection found three defects:

1. `onpromotion` is 0 for every row from 2013-01 to 2014-03, then promotions appear abruptly (1,939 in 2014-04, 69,662 by 2014-07). These are unrecorded values, not true zeros.
2. Stores close on Dec 25: the data has 1,685 distinct dates over 1,688 calendar days.
3. The 2016-04-16 Manabí earthquake causes a weeks-long demand shock but is stored as an ordinary national "Event" in `holidays_events.csv`.

## Decision

- **Default dataset stays Favorita.** M5 (item × store, many zero-sales days, licence unverified) and Rossmann (no product dimension) were rejected.
- **Training window starts 2014-04-01** for every model configuration (production, CV, every ablation arm), so configurations are compared on identical data. The start date is configuration (`TRAINING_START_DATE`), not hard-coded in queries.
- **Closure days are excluded from history** (rows absent, not `y = 0`). Prophet handles missing dates natively. Baselines treat a missing lag value by falling back to the most recent prior observation.
- **The earthquake is a distinct one-off holiday** in the Prophet `holidays` frame (`holiday = "earthquake_2016"`, `upper_window ≈ 30`), separate from recurring holidays, so its effect is not projected onto future holidays.

## Consequences

- About 3.4 years of usable history (2014-04-01 → 2017-08-15) instead of about 4.6. This is enough for yearly seasonality and the 3-fold CV minimum, but long CV horizons will have fewer folds.
- The sample-data generator path must still work: it has no promo gap, so the window start must be optional (`None` = use all data).
- README must state the window and why, so the trimmed history isn't mistaken for a bug.
