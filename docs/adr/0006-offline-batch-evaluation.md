# ADR-0006: Evaluation runs as an offline batch job; the API only reads results

- **Status:** Accepted
- **Date:** 2026-11-11
- **Change:** `improve-forecasting-evaluation-and-inventory`
- **Supersedes:** design.md decision 7 ("training runs synchronously in the request" for evaluation); tasks.md 5.3 (`POST /api/evaluate/<id>`)

## Context

A full evaluation (5 ablation arms × about 13 folds, ADR-0005) is about 65 Prophet fits, roughly 1–2 minutes per product, for about 33 products. That exceeds dev-proxy and WSGI worker timeouts and would block a worker meanwhile. The dataset is static, so results only change when data is re-imported or evaluation config changes.

## Decision

- **CLI:** `python -m evaluate --all | --product <id>` runs rolling CV, baselines and the regressor ablation, using process-level parallelism. It writes evaluation results and the **selected configuration** per product.
- **Docker Compose:** a one-off `evaluate` service runs after the import. README task 3.7 findings are produced by this same command.
- **API is read-only for evaluation:** `GET /api/accuracy/<id>` serves stored results. There is no `POST /api/evaluate/<id>`. If a product has never been evaluated, the API returns `404` with a message saying to run the evaluation command.
- **Production forecasts** (`POST /api/forecast`, still synchronous, one fit) use the product's selected configuration if one exists, otherwise the **default configuration: holidays only**. The response includes `config_source: "selected" | "default"` and the configuration used.
- Stored evaluation records the training window, CV parameters and a data fingerprint (row count plus max date), so stale results can be detected after a re-import.

## Alternatives considered

- **Background thread plus status polling:** allows re-evaluation from the UI but adds job state, failure and restart handling, and multi-worker issues, all for a computation that runs once on static data.
- **Synchronous request:** times out.

## Consequences

- The UI cannot trigger evaluation. The accuracy panel shows an empty state with instructions when results are missing.
- The "status exposed for a future job queue" seam in the design is no longer needed. A queue could later call the same `evaluate` entry point.
- The forecast-persistence spec's "Accuracy read" scenario stands. A "Not yet evaluated" scenario is added.
