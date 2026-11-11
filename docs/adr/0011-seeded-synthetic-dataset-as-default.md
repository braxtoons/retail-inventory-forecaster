# ADR-0011: A seeded, Favorita-shaped synthetic dataset is the out-of-the-box default; Favorita is opt-in

- **Status:** Accepted
- **Date:** 2026-11-11
- **Change:** `improve-forecasting-evaluation-and-inventory`
- **Refines:** ADR-0003 (Favorita remains the dataset for documented results)

## Context

The Kaggle CSVs (120 MB) are git-ignored and should not be redistributed, so a fresh clone running `docker compose up` has no Favorita data. The existing `generate_sample_data.py` has no oil, holiday or promo data, no closure days, an unseeded RNG, and dates ending on wall-clock today. None of the evaluation, ablation or inventory decisions can be exercised with it.

## Decision

Rewrite `generate_sample_data.py` as a **seeded synthetic generator shaped like Favorita**, writing to the same tables the Kaggle importer uses:

- Fixed date range ending at a fixed **as-of date** (config), about 3 years long.
- Weekly and yearly seasonality, trend, noise; at least one **weighed product with fractional quantities** (ADR-0001).
- **Holidays table** using the ADR-0004 types: several recurring holidays with known effects, one transferred holiday with its `Transfer` row, one bridge and work day, one one-off shock event.
- **Promotions with a known positive effect**, plus a `planned_promotions` window after the as-of date (ADR-0002).
- **Oil price as a random walk with no effect on demand.**
- **Dec 25 closures** (rows absent).
- `TRAINING_START_DATE = None` for this dataset (no promo gap, ADR-0003).

Docker Compose loads synthetic data by default. Favorita is loaded through an opt-in profile (`docker compose --profile kaggle up`) that mounts `data/store-sales` and runs the importer.

## Alternatives considered

- **Keep the generator as a test fixture only:** a fresh clone shows an empty app until the user downloads Kaggle data by hand.
- **Delete the generator:** same, with no fallback.

## Consequences

- **Ground-truth integration tests** become possible and are required:
  - the ablation selects a configuration that includes promo and excludes oil;
  - the holiday mapping drops the transferred date;
  - closure days are absent from training data;
  - achieved service level is near the target on well-specified data.
- The synthetic data's parameters are documented so the README can explain what "correct" looks like.
- `setup.sh`, README and QUICKSTART are updated to the new default and the Kaggle profile.
- The README is clear that the headline accuracy findings (task 3.7) come from Favorita, not synthetic data.
