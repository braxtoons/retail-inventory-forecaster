## ADDED Requirements

### Requirement: Persisted forecast runs
The system SHALL store each generated forecast as a run covering the full 90-day maximum horizon. A run SHALL include:
- its configuration and configuration source;
- random seed;
- as-of date;
- `promo_known_through`;
- data fingerprint;
- daily forecasts with 95% bounds;
- 1000 cumulative demand sample paths.

The run, its daily rows and its samples SHALL be written in one transaction. Only the latest 5 runs per product are kept.

#### Scenario: Cached read
- **WHEN** a client requests the forecast for a product that has a stored run, with any `forecast_days` from 1 to 90
- **THEN** the system returns the first `forecast_days` days of the latest run without training a model

#### Scenario: Regenerate
- **WHEN** a client POSTs to generate a forecast
- **THEN** the system trains, stores a new run atomically, prunes runs beyond the latest 5, and returns the new run

### Requirement: Configuration source
The system SHALL generate forecasts with the product's selected configuration from its latest evaluation run, or with the default configuration (holidays only) when the product has not been evaluated. It SHALL report which was used.

#### Scenario: Unevaluated product
- **WHEN** a forecast is generated for a product with no evaluation run
- **THEN** the run uses holidays only and the response has `config_source: "default"`

### Requirement: Stale runs
The system SHALL mark a forecast run as stale when its configuration differs from the product's current selected configuration, or its data fingerprint differs from the current data. It SHALL NOT retrain on read.

#### Scenario: Evaluation after forecast
- **WHEN** a product is evaluated and a different configuration is selected after its latest forecast run was created
- **THEN** reading the forecast returns that run with `stale: true` and a `stale_reason`

### Requirement: Forecast response metadata
Forecast responses SHALL include:
- run id and creation time;
- as-of date;
- configuration and `config_source`;
- `promo_known_through`;
- `stale`;
- the seasonal-naive reference series for the displayed horizon.

#### Scenario: Metadata present
- **WHEN** a client reads or generates a forecast
- **THEN** all metadata fields above are present

### Requirement: Persisted evaluation results
The system SHALL store each evaluation run with:
- CV parameters, training start and data fingerprint;
- metric rows per model or ablation arm, fold, fold set (selection/test) and horizon bucket;
- calibration rows;
- the selected configuration.

The current selected configuration of a product is that of its latest evaluation run.

#### Scenario: Accuracy read
- **WHEN** a client requests accuracy for an evaluated product
- **THEN** the system returns the latest evaluation's test-fold metrics for Prophet and both baselines, skill and verdict per bucket, per-fold values, the labelled ablation table, achieved service level, and the evaluation timestamp

### Requirement: Safe error handling and validation
The system SHALL validate request inputs and SHALL NOT expose internal exception text to clients.

#### Scenario: Unexpected failure
- **WHEN** an unexpected server error occurs
- **THEN** the client receives a generic 500 message and the details are logged server-side

#### Scenario: Invalid forecast horizon
- **WHEN** `forecast_days` is not an integer from 1 to 90
- **THEN** the system returns 400

### Requirement: Reproducible environment and tests
The repository SHALL provide:
- a Docker Compose setup that loads the seeded synthetic dataset by default and Favorita through an opt-in `kaggle` profile;
- a backend test suite in `unit`, `db` and `slow` tiers;
- a frontend built with Vite and TypeScript using shadcn/ui components, with a Vitest component test suite;
- CI running all backend tiers, the frontend tests and type check, and the frontend build.

#### Scenario: Fresh setup
- **WHEN** a developer runs `docker compose up` on a fresh clone
- **THEN** Postgres, the backend and the frontend start with the schema applied, synthetic data loaded, and evaluation results available

#### Scenario: Fast local loop
- **WHEN** a developer runs `pytest -m "not slow"`
- **THEN** no Prophet model is fitted
