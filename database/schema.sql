-- Create database (run manually if needed)
-- CREATE DATABASE retail_forecaster;

-- Products table
CREATE TABLE IF NOT EXISTS products (
    product_id SERIAL PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    unit_price DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sales data table (time-series)
CREATE TABLE IF NOT EXISTS sales_data (
    sale_id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(product_id),
    sale_date DATE NOT NULL,
    quantity_sold NUMERIC(12, 3) NOT NULL,
    total_amount DECIMAL(10, 2),
    on_promotion INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for time-series queries
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_data(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_product_date ON sales_data(product_id, sale_date);

-- Oil prices table (external regressor)
CREATE TABLE IF NOT EXISTS oil_prices (
    oil_id SERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    dcoilwtico DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_oil_date ON oil_prices(date);

-- Holidays table (external regressor)
CREATE TABLE IF NOT EXISTS holidays (
    holiday_id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    type VARCHAR(50),
    locale VARCHAR(50),
    locale_name VARCHAR(100),
    description VARCHAR(255),
    transferred BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_holiday_date ON holidays(date);

-- Forecasts table
CREATE TABLE IF NOT EXISTS forecasts (
    forecast_id SERIAL PRIMARY KEY,
    product_id INTEGER REFERENCES products(product_id),
    forecast_date DATE NOT NULL,
    predicted_quantity DECIMAL(10, 2) NOT NULL,
    lower_bound DECIMAL(10, 2),
    upper_bound DECIMAL(10, 2),
    confidence_level DECIMAL(5, 2) DEFAULT 95.0,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for forecast queries
CREATE INDEX IF NOT EXISTS idx_forecast_product_date ON forecasts(product_id, forecast_date);

-- ---------------------------------------------------------------------------
-- Migration for change `improve-forecasting-evaluation-and-inventory`.
-- Everything below is idempotent and safe to re-run on an existing database.
-- ---------------------------------------------------------------------------

-- Fractional quantities for weighed families (ADR-0001). Widening is safe for existing integers.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'sales_data'
          AND column_name = 'quantity_sold' AND data_type = 'integer'
    ) THEN
        ALTER TABLE sales_data ALTER COLUMN quantity_sold TYPE NUMERIC(12, 3);
    END IF;
END $$;

-- sale_date uniqueness is not enforced: the importers aggregate per (product, date) already.

-- Planned promotions: seed-only, no write API (ADR-0002)
CREATE TABLE IF NOT EXISTS planned_promotions (
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    date DATE NOT NULL,
    on_promotion NUMERIC(12, 3) NOT NULL DEFAULT 0,
    PRIMARY KEY (product_id, date)
);

-- Forecast runs (ADR-0010)
CREATE TABLE IF NOT EXISTS forecast_runs (
    run_id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    as_of_date DATE NOT NULL,
    config JSONB NOT NULL,
    config_source TEXT NOT NULL CHECK (config_source IN ('selected', 'default')),
    seed INTEGER NOT NULL,
    promo_known_through DATE,
    data_fingerprint TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_forecast_runs_product ON forecast_runs(product_id, created_at DESC);

ALTER TABLE forecasts ADD COLUMN IF NOT EXISTS run_id INTEGER REFERENCES forecast_runs(run_id) ON DELETE CASCADE;
-- Legacy forecasts (no run) cannot be served by the new API.
DELETE FROM forecasts WHERE run_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_forecasts_run ON forecasts(run_id, forecast_date);

CREATE TABLE IF NOT EXISTS forecast_run_samples (
    run_id INTEGER PRIMARY KEY REFERENCES forecast_runs(run_id) ON DELETE CASCADE,
    cumulative_paths REAL[][] NOT NULL
);

-- Evaluation runs (ADR-0010). The latest run per product carries its selected configuration.
CREATE TABLE IF NOT EXISTS evaluation_runs (
    eval_id SERIAL PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cv_params JSONB NOT NULL,
    training_start DATE,
    data_fingerprint TEXT NOT NULL,
    selected_config JSONB NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evaluation_runs_product ON evaluation_runs(product_id, created_at DESC);

-- fold_cutoff IS NULL marks the row pooled across the folds of its fold_set.
CREATE TABLE IF NOT EXISTS evaluation_metrics (
    eval_id INTEGER NOT NULL REFERENCES evaluation_runs(eval_id) ON DELETE CASCADE,
    model TEXT NOT NULL,
    arm TEXT,
    fold_cutoff DATE,
    fold_set TEXT NOT NULL CHECK (fold_set IN ('selection', 'test')),
    horizon_bucket TEXT NOT NULL,
    mae DOUBLE PRECISION,
    rmse DOUBLE PRECISION,
    wape DOUBLE PRECISION,
    mape DOUBLE PRECISION,
    mape_excluded INTEGER,
    coverage DOUBLE PRECISION,
    n INTEGER
);
CREATE INDEX IF NOT EXISTS idx_evaluation_metrics_eval ON evaluation_metrics(eval_id);

CREATE TABLE IF NOT EXISTS evaluation_service_level (
    eval_id INTEGER NOT NULL REFERENCES evaluation_runs(eval_id) ON DELETE CASCADE,
    fold_cutoff DATE NOT NULL,
    lead_time INTEGER NOT NULL,
    alpha NUMERIC(6, 4) NOT NULL,
    hit BOOLEAN NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_evaluation_sl_eval ON evaluation_service_level(eval_id);
