## ADDED Requirements

### Requirement: Daily demand series per product
The system SHALL produce one daily demand series per product, where `y` equals the sum of that product's sales on that date across all stores, with no row duplication from joins against other tables.

#### Scenario: Date with multiple national holiday rows
- **WHEN** a date has more than one national holiday row (e.g. 2016-05-01)
- **THEN** that date's `y` equals the raw sum of sales for that date, not a multiple of it

### Requirement: Fractional quantities preserved
The system SHALL store and forecast demand as non-integer quantities and SHALL NOT truncate or round sales on import.

#### Scenario: Weighed product import
- **WHEN** Favorita sales for a weighed family (e.g. PRODUCE) contain fractional values
- **THEN** the stored daily quantity equals the fractional sum to 3 decimal places

### Requirement: Training window
The system SHALL fit and evaluate models only on history on or after a configurable training start date, applied identically to production forecasts, every CV fold and every ablation arm. An unset start date means all history.

#### Scenario: Favorita promotion gap
- **WHEN** the Favorita dataset is loaded with the default configuration
- **THEN** no model sees history before 2014-04-01

### Requirement: Closure days are missing, not zero
The system SHALL treat dates on which no sales are recorded for any product (store closures) as missing observations, not zero demand.

#### Scenario: Christmas closure
- **WHEN** Dec 25 has no sales rows
- **THEN** the training series has no row for Dec 25 and no metric scores Dec 25

### Requirement: Holiday frame mapping
The system SHALL supply holidays to Prophet only through its `holidays` parameter, built from national holiday rows using these rules:
- `Holiday` rows with `transferred = true` are dropped;
- `Transfer` rows take the original holiday's name;
- `Additional` rows and recurring `Event` rows are named by description;
- `Bridge` rows are named `bridge`, and `Work Day` rows `work_day`;
- regional and local rows are ignored.

#### Scenario: Transferred holiday
- **WHEN** a holiday is marked transferred and has a corresponding `Transfer` row
- **THEN** the original date is absent from the holidays frame and the transfer date appears under the original holiday's name

#### Scenario: Future holiday in horizon
- **WHEN** a recurring national holiday falls within the forecast horizon
- **THEN** the forecast includes that holiday's learned effect

### Requirement: Shock events
The system SHALL model one-off disruptions (2016 Manabí earthquake, 2014 World Cup) as distinct non-recurring holidays so their effect is not projected onto future dates.

#### Scenario: Earthquake does not recur
- **WHEN** a forecast is generated for dates after the earthquake window
- **THEN** no earthquake effect is applied to those dates

### Requirement: Regressor knowledge policy
The system SHALL build future regressor values with one shared function used by both production forecasts and CV folds:
- holidays from the calendar;
- promotions from planned promotions, 0 where none are planned;
- oil price as the last observed value at or before the as-of date, carried forward.

#### Scenario: Oil in a CV fold
- **WHEN** a CV fold with cutoff C is evaluated with oil enabled
- **THEN** every future oil value in that fold equals the last observed oil price on or before C

#### Scenario: Production and CV parity
- **WHEN** the future frame is built for as-of date D by production and by CV with cutoff D on the same history
- **THEN** the two frames are identical

### Requirement: Planned promotions
The system SHALL store planned promotions per product and date, seeded at import (Favorita: from `test.csv`), SHALL NOT expose a write API for them, and SHALL report `promo_known_through` (the last planned-promotion date) with forecasts.

#### Scenario: Horizon beyond planned promotions
- **WHEN** a forecast horizon extends past `promo_known_through`
- **THEN** promotions are 0 for later dates and the response includes `promo_known_through`

### Requirement: Seeded synthetic dataset
The system SHALL provide a deterministic synthetic data generator, shaped like Favorita, that populates the same tables as the Favorita importer. It SHALL include:
- a fixed as-of date;
- weekly and yearly seasonality;
- at least one fractional product;
- Dec 25 closures;
- holiday rows of every mapped type, including one shock event;
- promotions with a known positive effect and a planned-promotion window;
- an oil random walk with no effect on demand.

#### Scenario: Reproducibility
- **WHEN** the generator runs twice with the same seed
- **THEN** the resulting tables are identical
