# ADR-0009: Stock-out risk as a probability from sample paths, with levels tied to the service level

- **Status:** Accepted
- **Date:** 2026-11-11
- **Change:** `improve-forecasting-evaluation-and-inventory`
- **Supersedes:** inventory-recommendations spec "Stock-out risk" (on-hand < cumulative lower bound → high)

## Context

The spec flagged "high" risk only when on-hand fell below the cumulative *lower bound* of lead-time demand. That is near-certain stock-out, too late to be useful. It defined no other levels, no probability, and no rule for the projected stock-out date.

## Decision

Using the sample paths from ADR-0008, with user-supplied on-hand (≥ 0) at the as-of date:

- **Stock-out probability** P = share of paths whose cumulative demand over days 1..L exceeds on-hand.
- **Risk level:**
  - `ok` if P ≤ 1 − α (equivalent to on-hand ≥ reorder point);
  - `elevated` if 1 − α < P < 0.5;
  - `high` if P ≥ 0.5.
- **`reorder_now`** = on-hand ≤ reorder point.
- **Projected stock-out date** = first day the **median** cumulative path exceeds on-hand, searched over the full forecast horizon (≤ 90 days). **Earliest likely date** = the same using the **90th-percentile** cumulative path. If not reached, the value is `null` and `beyond_horizon: true`.
- **Inventory position = on-hand only.** Stock already on order is out of scope. The response includes an `assumptions` list stating this.

## Alternatives considered

- **Binary flag (on-hand < ROP):** discards the probability the sample paths give for free.
- **Model on-order quantities:** needs per-order arrival dates the project has no source for.

## Consequences

- Risk levels can never contradict the reorder recommendation: below ROP is always at least `elevated`.
- The cumulative paths for the whole horizon must be available at read time (see the persistence decision).
- Tests: P is monotone non-increasing in on-hand; on-hand = ROP gives `ok`; on-hand = 0 with positive demand gives `high` and a stock-out date of day 1.
