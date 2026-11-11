# ADR-0004: Mapping Kaggle holiday types to the Prophet holidays frame

- **Status:** Accepted
- **Date:** 2026-11-11
- **Change:** `improve-forecasting-evaluation-and-inventory`
- **Refines:** design.md decision 5 ("Holidays use Prophet's `holidays` dataframe")

## Context

`holidays_events.csv` has seven national row types, and the current code treats every national row as `is_holiday = 1`. That is wrong for transferred holidays (not a day off) and make-up work days, and it merges one-off events into recurring effects. The current SQL join on `holidays` also **double-counts sales** on the six dates that have two national rows (e.g. 2016-05-01, 2016-05-08, 2014-12-26).

## Decision

The holidays frame is built from Kaggle national rows only, with this mapping:

| Kaggle type | Handling | Prophet `holiday` name |
|---|---|---|
| `Holiday`, `transferred=False` | keep | description |
| `Holiday`, `transferred=True` | **drop** (normal day that year) | — |
| `Transfer` | keep on observed date | original holiday's name (strip `Traslado `) |
| `Additional` | keep | description (e.g. `Navidad-1`), so each offset day has its own effect |
| `Bridge` | keep | `bridge` |
| `Work Day` | keep | `work_day` |
| `Event`: Black Friday, Cyber Monday, Día de la Madre | keep | description (strip `±N` suffix) |
| `Event`: Mundial 2014 | shock event | `world_cup_2014` |
| `Event`: Terremoto Manabí | shock event | `earthquake_2016` (ADR-0003) |
| Regional / Local | ignore | — |

Holidays are never joined into the sales query. They are supplied only via Prophet's `holidays=` parameter.

## Alternatives considered

- **Prophet `add_country_holidays('EC')`:** no transfers, bridges, work days or events. Rejected.
- **Keep the binary `is_holiday` regressor:** cannot separate effects, and a future 0/1 column is easy to get wrong. Rejected (design decision 5).

## Consequences

- A regression test asserts that per-date `y` equals the raw per-date sales sum, including on dates with multiple national holiday rows.
- Recurring holidays with few occurrences in the training window will have noisy effects. Prophet's `holidays_prior_scale` regularises them.
- Regional holidays are ignored. This is acceptable for chain-wide family totals (ADR-0001) and must be revisited if per-store forecasting is ever added.
