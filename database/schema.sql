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
    quantity_sold INTEGER NOT NULL,
    total_amount DECIMAL(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for time-series queries
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales_data(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_product_date ON sales_data(product_id, sale_date);

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
