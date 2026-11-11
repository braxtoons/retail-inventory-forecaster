## ADDED Requirements

### Requirement: Reorder point and safety stock from sample paths
The system SHALL compute lead-time demand for a product from the latest forecast run's stored cumulative demand sample paths (daily values clipped at 0). It SHALL set:
- reorder point = the α-quantile of cumulative demand at day L;
- safety stock = reorder point − mean cumulative demand at day L.

Here α is the cycle service level and L the lead time. Recommendations refer to stock at the single distribution centre.

#### Scenario: Default parameters
- **WHEN** a recommendation is requested without parameters
- **THEN** the system uses a 7-day lead time and 0.95 service level and returns safety stock, reorder point, mean lead-time demand, and the parameters used

#### Scenario: Higher service level
- **WHEN** the service level increases with all else equal
- **THEN** safety stock and reorder point do not decrease

#### Scenario: No training on read
- **WHEN** a recommendation is requested for a product with a stored forecast run
- **THEN** no model is trained

#### Scenario: No forecast run
- **WHEN** a recommendation is requested for a product with no forecast run
- **THEN** the system returns 404 asking for a forecast to be generated first

### Requirement: Stock-out probability and risk level
Given an on-hand quantity at the as-of date, the system SHALL compute P, the share of sample paths whose cumulative demand at day L exceeds on-hand. It SHALL assign a risk level:
- `ok` when P ≤ 1 − α;
- `elevated` when 1 − α < P < 0.5;
- `high` when P ≥ 0.5.

It SHALL return `reorder_now` = on-hand ≤ reorder point.

#### Scenario: On-hand at reorder point
- **WHEN** on-hand equals the reorder point
- **THEN** risk is `ok` and `reorder_now` is true

#### Scenario: No stock
- **WHEN** on-hand is 0 and forecast demand is positive
- **THEN** risk is `high` and the projected stock-out date is the first forecast day

#### Scenario: Monotone in on-hand
- **WHEN** on-hand increases with all else equal
- **THEN** stock-out probability does not increase

### Requirement: Projected stock-out dates
The system SHALL return the first forecast day on which the median cumulative path exceeds on-hand (projected stock-out date), and the first day on which the 90th-percentile cumulative path exceeds it (earliest likely stock-out date). Both are searched over the full forecast horizon.

#### Scenario: Stock lasts beyond horizon
- **WHEN** neither path exceeds on-hand within the horizon
- **THEN** the dates are null and `beyond_horizon` is true

### Requirement: Stated assumptions and baseline warning
The system SHALL include in each recommendation an `assumptions` list stating:
- inventory position equals on-hand (no stock on order);
- quantities are at the distribution centre.

It SHALL include the 1–7-day verdict vs. seasonal-naive when the product has been evaluated.

#### Scenario: Forecast underperforms baseline
- **WHEN** the product's 1–7-day verdict is `worse`
- **THEN** the response includes the verdict so the UI can show a warning beside the reorder point, and the recommendation is still returned

### Requirement: Parameter validation
The system SHALL reject, with a 400 response and a descriptive message:
- lead times that are not integers from 1 to 90;
- service levels outside (0.5, 0.999);
- negative on-hand quantities.

#### Scenario: Invalid lead time
- **WHEN** lead time is 0, negative, or greater than 90
- **THEN** the system returns 400 with a descriptive message
