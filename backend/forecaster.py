import pandas as pd
from prophet import Prophet
from database import get_db_connection
from datetime import datetime, timedelta

class InventoryForecaster:
    def __init__(self):
        self.model = None

    def get_historical_data(self, product_id, days_back=730):
        """Fetch historical sales data for a product"""
        conn = get_db_connection()
        cur = conn.cursor()

        query = """
            SELECT sale_date as ds, SUM(quantity_sold) as y
            FROM sales_data
            WHERE product_id = %s
            AND sale_date >= CURRENT_DATE - INTERVAL '%s days'
            GROUP BY sale_date
            ORDER BY sale_date
        """

        cur.execute(query, (product_id, days_back))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Convert to DataFrame
        df = pd.DataFrame(rows)
        if not df.empty:
            df['ds'] = pd.to_datetime(df['ds'])

        return df

    def train_and_forecast(self, product_id, forecast_days=30):
        """Train Prophet model and generate forecasts"""
        # Get historical data
        df = self.get_historical_data(product_id)

        if df.empty or len(df) < 10:
            raise ValueError(f"Insufficient data for product {product_id}")

        # Initialize and train Prophet model
        self.model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.95  # 95% confidence interval
        )

        self.model.fit(df)

        # Create future dataframe
        future = self.model.make_future_dataframe(periods=forecast_days)

        # Make predictions
        forecast = self.model.predict(future)

        # Return only future predictions
        future_forecast = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].tail(forecast_days)

        return future_forecast

    def save_forecast(self, product_id, forecast_df):
        """Save forecast results to database"""
        conn = get_db_connection()
        cur = conn.cursor()

        # Clear old forecasts for this product
        cur.execute("DELETE FROM forecasts WHERE product_id = %s", (product_id,))

        # Insert new forecasts
        for _, row in forecast_df.iterrows():
            cur.execute(
                """
                INSERT INTO forecasts (product_id, forecast_date, predicted_quantity, lower_bound, upper_bound)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (product_id, row['ds'].date(), max(0, row['yhat']), max(0, row['yhat_lower']), max(0, row['yhat_upper']))
            )

        conn.commit()
        cur.close()
        conn.close()

    def generate_forecast_for_product(self, product_id, forecast_days=30):
        """Generate and save forecast for a specific product"""
        forecast = self.train_and_forecast(product_id, forecast_days)
        self.save_forecast(product_id, forecast)
        return forecast

    def get_accuracy_metrics(self, product_id):
        """Calculate historical accuracy metrics"""
        # Use more data for better accuracy - at least 1 year
        df = self.get_historical_data(product_id, days_back=540)

        if df.empty or len(df) < 100:
            return None

        # Train on first 80% of data
        split_idx = int(len(df) * 0.8)
        train_df = df[:split_idx]
        test_df = df[split_idx:]

        # Train model
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False
        )
        model.fit(train_df)

        # Predict on test set
        forecast = model.predict(test_df[['ds']])

        # Calculate metrics
        actual = test_df['y'].values
        predicted = forecast['yhat'].values

        mae = abs(actual - predicted).mean()
        mape = (abs((actual - predicted) / actual) * 100).mean()

        return {
            'mae': float(mae),
            'mape': float(mape)
        }

if __name__ == '__main__':
    # Test the forecaster
    forecaster = InventoryForecaster()
    forecast = forecaster.generate_forecast_for_product(product_id=1, forecast_days=30)
    print(forecast)
