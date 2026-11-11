# ADR-0013: Three pytest tiers; CI runs real Prophet on reduced synthetic data

- **Status:** Accepted
- **Date:** 2026-11-11
- **Change:** `improve-forecasting-evaluation-and-inventory`
- **Refines:** design.md decision 8

## Context

The central claims of this change are end to end: CV scores what ships (ADR-0002), the ablation keeps useful regressors and drops useless ones (ADR-0007, ADR-0011), and inventory quantiles are calibrated (ADR-0008). Checking them needs real Prophet fits, which are slow (≈ 0.5–2 s each, about 48 per product for a full evaluation). `prophet==1.1.5` ships a precompiled Stan model, so no compile step is needed in Docker or CI.

## Decision

- **pytest markers:**
  - `unit`: pure functions with no database and no fit. Covers metrics, inventory maths and risk levels, holiday mapping, fold generation and selection/test split, `build_future_frame` parity between CV and production, the ablation rule on synthetic scores, and `build_model` registering regressors and holidays.
  - `db`: Postgres service. Covers queries (including the holiday double-count regression), migrations, atomic run writes and pruning, staleness, and API tests via Flask's test client with a fake model behind the `build_model` interface.
  - `slow`: real Prophet on the seeded synthetic dataset with a reduced test config (2 products, `uncertainty_samples = 200`, short fold layout). Covers ADR-0011 ground-truth assertions and an end-to-end forecast → inventory path.
- **CI (GitHub Actions)** on every push and PR runs all three tiers with a Postgres service, plus the frontend component tests and `npm run build`. Locally, `pytest -m "not slow"` is the fast loop.
- **Frontend tests:** Vitest + jsdom + `@testing-library/react` (replaces CRA's Jest, per ADR-0014). Panel tests cover loaded, not-evaluated, error, stale and `worse`-verdict states with mocked fetches.
- **Determinism:** NumPy's global random generator is seeded with the run's `seed` immediately before `predictive_samples`. Slow tests assert within tolerances, not exact values.
- **Backend image:** `python:3.11-slim`, Prophet installed from its wheel.

## Alternatives considered

- **Skip real fits in CI and run the slow tier by hand:** faster CI, but nothing automatically checks the change's end-to-end claims.

## Consequences

- CI time is dominated by the slow tier, a few minutes. If it grows, the slow tier moves to a nightly or main-only workflow. That is a config change, not a redesign.
- The model seam (`build_model` returning an object with `fit`/`predict`/`predictive_samples`) must stay narrow enough to fake.
