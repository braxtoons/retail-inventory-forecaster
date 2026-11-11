# ADR-0001: Inventory is modelled as held at a single distribution centre, per product family

- **Status:** Accepted
- **Date:** 2026-11-11
- **Change:** `improve-forecasting-evaluation-and-inventory`

## Context

The Kaggle import builds each "product" by summing a product family's sales across all 54 stores. The `inventory-recommendations` capability then gives each product a reorder point, safety stock and on-hand quantity. A chain-wide family total has no real stock decision behind it unless we say where that stock is held.

## Decision

- A **product** is a product family aggregated across all stores (one forecast series per family).
- All inventory quantities refer to a notional **single distribution centre (DC)** that supplies the chain. Recommendations are expressed as DC stock of that family.
- Weighed families keep fractional quantities end to end: `sales_data.quantity_sold` becomes `NUMERIC`, and the importer stops truncating with `int()`.

## Alternatives considered

- **Per store × family forecasting:** realistic, but 54 × 33 = 1,782 series makes rolling CV plus regressor ablation impractical. Already a non-goal in the design; it stays a possible follow-up.
- **Leave "product" undefined:** rejected because the inventory outputs would imply a stock decision that does not exist.

## Consequences

- Safety stock computed at DC level reflects pooled (aggregated) variability. It is lower than the sum of per-store safety stocks would be, and the README must say so.
- UI and API copy must not imply per-store or per-SKU recommendations.
- Schema change: `quantity_sold INTEGER` → `NUMERIC(12,3)`. This is added to the additive migration (task 1.3), along with re-running the import.
