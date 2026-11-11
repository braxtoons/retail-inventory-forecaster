# ADR-0005: 90-day maximum horizon; evaluation at a fixed horizon, reported by horizon bucket

- **Status:** Accepted
- **Date:** 2026-11-11
- **Change:** `improve-forecasting-evaluation-and-inventory`
- **Supersedes:** design.md decision 2 horizon defaults ("horizon = requested forecast days capped at 30"); forecast-persistence spec `forecast_days` range 1–365

## Context

- Favorita history ends 2017-08-15, the holiday calendar ends 2017-12-26, and planned promotions end 2017-08-31. A 365-day forecast would contain no holidays in 2018.
- The design tied CV horizon to the requested horizon (capped at 30), so a 180-day forecast showed 30-day accuracy.
- Evaluation is persisted per product, so it cannot depend on a request parameter.

## Decision

- **Maximum forecast horizon = 90 days** (`MAX_FORECAST_DAYS`, config). `forecast_days` must be an integer from 1 to 90, else 400. 90 days from the as-of date stays inside the holiday calendar.
- **Evaluation always runs at the maximum horizon (90 days)**, independent of any request. It uses `initial = 365` days, `horizon = 90`, `period = 60` (all config), giving about 13 folds over the 2014-04-01 → 2017-08-15 window.
- **Metrics are reported per horizon bucket, 1–7, 8–30 and 31–90 days**, plus overall. The UI shows the buckets covered by the requested horizon. Inventory recommendations cite the 1–7 bucket.
- **As-of date** = last date in the product's history. Forecasts start the day after it. User-supplied on-hand is interpreted as stock at the as-of date. The UI shows the as-of date prominently.

## Alternatives considered

- **Keep 365 days and fill 2018 holidays from the `holidays` package:** brings back the transfer/bridge errors fixed in ADR-0004.
- **Evaluate separately per requested horizon:** more fits for information the buckets already give, and incompatible with per-product caching.

## Consequences

- About 65 Prophet fits per product for a full ablation (5 arms × about 13 folds). This is too slow for a synchronous request; see the evaluation execution decision.
- The 3-fold minimum now means at least `initial + horizon + 2 × period` = 575 days of history.
- If a longer holiday calendar is loaded later, the cap could be derived from calendar coverage instead of a constant.
