from flask import Flask, jsonify, request
from flask_cors import CORS
from database import get_db_connection
from forecaster import InventoryForecaster
from config import Config
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)
app.config.from_object(Config)

forecaster = InventoryForecaster()

@app.route('/api/products', methods=['GET'])
def get_products():
    """Get list of all products"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT product_id, product_name, category, unit_price FROM products ORDER BY product_name")
        products = cur.fetchall()

        cur.close()
        conn.close()

        return jsonify(products), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/historical', methods=['GET'])
def get_historical_data():
    """Get historical sales data for a product"""
    try:
        product_id = request.args.get('product_id', type=int)
        days_back = request.args.get('days_back', default=90, type=int)

        if not product_id:
            return jsonify({'error': 'product_id is required'}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # Get the most recent N days of available data (works with old datasets)
        query = """
            SELECT
                sale_date,
                SUM(quantity_sold) as quantity_sold,
                SUM(total_amount) as total_amount
            FROM sales_data
            WHERE product_id = %s
            AND sale_date >= (
                SELECT MAX(sale_date) - INTERVAL '%s days'
                FROM sales_data
                WHERE product_id = %s
            )
            GROUP BY sale_date
            ORDER BY sale_date
        """

        cur.execute(query, (product_id, days_back, product_id))
        historical_data = cur.fetchall()

        cur.close()
        conn.close()

        # Convert dates to strings for JSON serialization
        for record in historical_data:
            record['sale_date'] = record['sale_date'].isoformat()

        return jsonify(historical_data), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/forecast', methods=['POST'])
def generate_forecast():
    """Generate forecast for a product"""
    try:
        data = request.get_json()
        product_id = data.get('product_id')
        forecast_days = data.get('forecast_days', 30)

        if not product_id:
            return jsonify({'error': 'product_id is required'}), 400

        # Generate forecast
        forecast_df = forecaster.generate_forecast_for_product(product_id, forecast_days)

        # Convert to list of dicts for JSON
        forecast_list = []
        for _, row in forecast_df.iterrows():
            forecast_list.append({
                'forecast_date': row['ds'].isoformat(),
                'predicted_quantity': float(row['yhat']),
                'lower_bound': float(row['yhat_lower']),
                'upper_bound': float(row['yhat_upper'])
            })

        return jsonify({
            'product_id': product_id,
            'forecast': forecast_list
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/forecast/<int:product_id>', methods=['GET'])
def get_saved_forecast(product_id):
    """Get saved forecast for a product"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = """
            SELECT
                forecast_date,
                predicted_quantity,
                lower_bound,
                upper_bound,
                confidence_level,
                generated_at
            FROM forecasts
            WHERE product_id = %s
            ORDER BY forecast_date
        """

        cur.execute(query, (product_id,))
        forecasts = cur.fetchall()

        cur.close()
        conn.close()

        # Convert dates to strings for JSON serialization
        for record in forecasts:
            record['forecast_date'] = record['forecast_date'].isoformat()
            record['generated_at'] = record['generated_at'].isoformat()

        return jsonify(forecasts), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/accuracy/<int:product_id>', methods=['GET'])
def get_accuracy(product_id):
    """Get accuracy metrics for a product's forecast"""
    try:
        metrics = forecaster.get_accuracy_metrics(product_id)

        if metrics is None:
            return jsonify({'error': 'Insufficient data for accuracy calculation'}), 400

        return jsonify(metrics), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=Config.FLASK_PORT, debug=Config.DEBUG)
