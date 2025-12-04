import pandas as pd
from prophet import Prophet
from database import get_db_connection
from datetime import datetime, timedelta

class InventoryForecaster:
    def __init__(self):
        self.model = None

    def get_historical_data(self, product_id, days_back=None):
        """Fetch historical sales data for a product with external regressors

        Args:
            product_id: ID of the product
            days_back: Number of days back to fetch, or None for all data
        """
        conn = get_db_connection()
        cur = conn.cursor()

        if days_back is None:
            # Get all available data with regressors
            query = """
                SELECT
                    s.sale_date as ds,
                    SUM(s.quantity_sold) as y,
                    SUM(s.on_promotion) as on_promotion,
                    o.dcoilwtico as oil_price,
                    CASE WHEN h.date IS NOT NULL THEN 1 ELSE 0 END as is_holiday
                FROM sales_data s
                LEFT JOIN oil_prices o ON s.sale_date = o.date
                LEFT JOIN holidays h ON s.sale_date = h.date AND h.locale = 'National'
                WHERE s.product_id = %s
                GROUP BY s.sale_date, o.dcoilwtico, h.date
                ORDER BY s.sale_date
            """
            cur.execute(query, (product_id,))
        else:
            # Get data from last N days with regressors
            query = """
                SELECT
                    s.sale_date as ds,
                    SUM(s.quantity_sold) as y,
                    SUM(s.on_promotion) as on_promotion,
                    o.dcoilwtico as oil_price,
                    CASE WHEN h.date IS NOT NULL THEN 1 ELSE 0 END as is_holiday
                FROM sales_data s
                LEFT JOIN oil_prices o ON s.sale_date = o.date
                LEFT JOIN holidays h ON s.sale_date = h.date AND h.locale = 'National'
                WHERE s.product_id = %s
                AND s.sale_date >= CURRENT_DATE - INTERVAL '%s days'
                GROUP BY s.sale_date, o.dcoilwtico, h.date
                ORDER BY s.sale_date
            """
            cur.execute(query, (product_id, days_back))

        rows = cur.fetchall()
        cur.close()
        conn.close()

        # Convert to DataFrame
        df = pd.DataFrame(rows)
        if not df.empty:
            df['ds'] = pd.to_datetime(df['ds'])

            # Fill missing oil prices with forward fill then backward fill
            if 'oil_price' in df.columns:
                df['oil_price'] = df['oil_price'].fillna(method='ffill').fillna(method='bfill').fillna(0)

            # Ensure numeric columns
            df['on_promotion'] = df['on_promotion'].fillna(0).astype(float)
            df['is_holiday'] = df['is_holiday'].fillna(0).astype(int)

        return df

    def train_and_forecast(self, product_id, forecast_days=30):
        """Train Prophet model with external regressors and generate forecasts"""
        # Get historical data with regressors
        df = self.get_historical_data(product_id)

        if df.empty or len(df) < 10:
            raise ValueError(f"Insufficient data for product {product_id}")

        # Initialize Prophet model
        self.model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.95  # 95% confidence interval
        )

        # Add regressors if data available
        has_oil = 'oil_price' in df.columns and df['oil_price'].notna().any()
        has_holiday = 'is_holiday' in df.columns
        has_promo = 'on_promotion' in df.columns and df['on_promotion'].notna().any()

        if has_oil:
            self.model.add_regressor('oil_price')
        if has_holiday:
            self.model.add_regressor('is_holiday')
        if has_promo:
            self.model.add_regressor('on_promotion')

        # Fit model with available regressors
        self.model.fit(df[['ds', 'y'] + [col for col in ['oil_price', 'is_holiday', 'on_promotion'] if col in df.columns]])

        # Create future dataframe
        future = self.model.make_future_dataframe(periods=forecast_days)

        # Add future regressor values
        if has_oil:
            # Use last known oil price for future predictions
            last_oil_price = df['oil_price'].iloc[-1] if not df['oil_price'].isna().all() else 0
            future['oil_price'] = last_oil_price

        if has_holiday:
            # Get future holidays from database
            conn = get_db_connection()
            cur = conn.cursor()
            max_date = future['ds'].max().date()
            cur.execute(
                "SELECT date FROM holidays WHERE locale = 'National' AND date > %s AND date <= %s",
                (df['ds'].max().date(), max_date)
            )
            future_holidays = [row['date'] for row in cur.fetchall()]
            cur.close()
            conn.close()

            future['is_holiday'] = future['ds'].apply(lambda x: 1 if x.date() in future_holidays else 0)

        if has_promo:
            # Assume no future promotions (conservative forecast)
            future['on_promotion'] = 0

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
        # Get all available data for accuracy calculation
        df = self.get_historical_data(product_id)

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

        # Calculate MAPE excluding zero values to avoid division by zero
        non_zero_mask = actual != 0
        if non_zero_mask.sum() > 0:
            mape = (abs((actual[non_zero_mask] - predicted[non_zero_mask]) / actual[non_zero_mask]) * 100).mean()
        else:
            mape = 0.0

        return {
            'mae': float(mae),
            'mape': float(mape)
        }

if __name__ == '__main__':
    # Test the forecaster
    forecaster = InventoryForecaster()
    forecast = forecaster.generate_forecast_for_product(product_id=1, forecast_days=30)
    print(forecast)
