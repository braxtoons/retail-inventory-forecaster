import logging
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

import data
import evaluation as ev
import evaluation_store
import forecast_runs
import inventory
from config import Config
from database import get_cursor

log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)
app.config.from_object(Config)

NOT_EVALUATED_MESSAGE = ('This product has not been evaluated yet. '
                         'Run `python -m evaluate --product {pid}` (or `python -m evaluate --all`).')


# ---------------------------------------------------------------------------- errors / validation

class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.message, self.status = message, status


@app.errorhandler(ApiError)
def handle_api_error(err):
    return jsonify({'error': err.message}), err.status


@app.errorhandler(HTTPException)
def handle_http_error(err):
    return jsonify({'error': err.description}), err.code


@app.errorhandler(Exception)
def handle_unexpected(err):
    log.exception('Unhandled error on %s %s', request.method, request.path)   # details stay server-side
    return jsonify({'error': 'Internal server error'}), 500


def parse_int(value, name, lo=None, hi=None, default=None, required=False):
    """Strict integer parsing: '7' and 7 are fine; '7.5', 'abc', True and out-of-range values are 400."""
    if value is None or value == '':
        if required:
            raise ApiError(f'{name} is required')
        return default
    if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
        raise ApiError(f'{name} must be an integer')
    try:
        number = int(value) if not isinstance(value, str) else int(value.strip())
    except (TypeError, ValueError):
        raise ApiError(f'{name} must be an integer')
    if (lo is not None and number < lo) or (hi is not None and number > hi):
        raise ApiError(f'{name} must be between {lo} and {hi}')
    return number


def parse_float(value, name, default=None):
    if value is None or value == '':
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ApiError(f'{name} must be a number')
    if number != number or number in (float('inf'), float('-inf')):
        raise ApiError(f'{name} must be a finite number')
    return number


# ---------------------------------------------------------------------------- helpers

def _trim_forecast(run, forecast_days, reference):
    days = run['days'][:forecast_days]
    return [{
        'forecast_date': d['forecast_date'].isoformat(),
        'predicted_quantity': d['predicted_quantity'],
        'lower_bound': d['lower_bound'],
        'upper_bound': d['upper_bound'],
        'seasonal_naive': float(reference[i]) if i < len(reference) else None,
    } for i, d in enumerate(days)]


def _seasonal_naive_reference(run, product_id):
    """Seasonal-naive series for the stored run's horizon (value one week earlier, last observed week)."""
    as_of = ev.pd.Timestamp(run['as_of_date'])
    history = data.get_history(product_id, as_of=as_of.date())
    if history.empty:
        return []
    return ev.seasonal_naive_forecast(history, as_of, len(run['days']))


def _run_response(run, product_id, forecast_days):
    reference = _seasonal_naive_reference(run, product_id)
    return {
        'product_id': product_id,
        'run_id': run['run_id'],
        'created_at': run['created_at'],
        'as_of_date': run['as_of_date'],
        'config': run['config'],
        'config_source': run['config_source'],
        'promo_known_through': run['promo_known_through'],
        'stale': run['stale'],
        'stale_reason': run['stale_reason'],
        'forecast_days': forecast_days,
        'forecast': _trim_forecast(run, forecast_days, reference),
    }


# ---------------------------------------------------------------------------- routes

@app.route('/api/products', methods=['GET'])
def get_products():
    """List all products"""
    with get_cursor() as cur:
        cur.execute("SELECT product_id, product_name, category, unit_price::float8 AS unit_price "
                    "FROM products ORDER BY product_name")
        return jsonify(cur.fetchall()), 200


@app.route('/api/historical', methods=['GET'])
def get_historical_data():
    """Daily history for a product (most recent `days_back` days of available data)"""
    product_id = parse_int(request.args.get('product_id'), 'product_id', required=True)
    days_back = parse_int(request.args.get('days_back'), 'days_back', lo=1, hi=3650, default=90)

    with get_cursor() as cur:
        cur.execute("""
            SELECT sale_date,
                   SUM(quantity_sold)::float8 AS quantity_sold,
                   SUM(total_amount)::float8 AS total_amount
            FROM sales_data
            WHERE product_id = %s
              AND sale_date >= (SELECT MAX(sale_date) - make_interval(days => %s)
                                FROM sales_data WHERE product_id = %s)
            GROUP BY sale_date
            ORDER BY sale_date
        """, (product_id, days_back, product_id))
        rows = cur.fetchall()
    for r in rows:
        r['sale_date'] = r['sale_date'].isoformat()
    return jsonify(rows), 200


@app.route('/api/forecast', methods=['POST'])
def generate_forecast():
    """Train once and store a new 90-day forecast run; return it trimmed to forecast_days."""
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise ApiError('request body must be a JSON object')
    product_id = parse_int(body.get('product_id'), 'product_id', required=True)
    forecast_days = parse_int(body.get('forecast_days'), 'forecast_days', 1, Config.MAX_FORECAST_DAYS, default=30)
    try:
        run = forecast_runs.generate_run(product_id)
    except LookupError:
        raise ApiError('Product not found', 404)
    except forecast_runs.InsufficientData as exc:
        raise ApiError(str(exc), 400)
    return jsonify(_run_response(run, product_id, forecast_days)), 200


@app.route('/api/forecast/<int:product_id>', methods=['GET'])
def get_saved_forecast(product_id):
    """Latest stored run, trimmed to forecast_days. Never trains."""
    forecast_days = parse_int(request.args.get('forecast_days'), 'forecast_days', 1, Config.MAX_FORECAST_DAYS,
                              default=Config.MAX_FORECAST_DAYS)
    run = forecast_runs.latest_run(product_id)
    if run is None:
        raise ApiError('No forecast has been generated for this product yet. Generate one first.', 404)
    return jsonify(_run_response(run, product_id, forecast_days)), 200


@app.route('/api/accuracy/<int:product_id>', methods=['GET'])
def get_accuracy(product_id):
    """Stored evaluation results (read-only; evaluation runs offline)."""
    accuracy = evaluation_store.load_latest_evaluation(product_id)
    if accuracy is None:
        raise ApiError(NOT_EVALUATED_MESSAGE.format(pid=product_id), 404)
    return jsonify(accuracy), 200


@app.route('/api/inventory/<int:product_id>', methods=['GET'])
def get_inventory(product_id):
    """Reorder point, safety stock and stock-out risk from the latest forecast run's sample paths."""
    lead_time = parse_int(request.args.get('lead_time'), 'lead_time', default=Config.DEFAULT_LEAD_TIME)
    service_level = parse_float(request.args.get('service_level'), 'service_level',
                                default=Config.DEFAULT_SERVICE_LEVEL)
    on_hand = parse_float(request.args.get('on_hand'), 'on_hand')
    try:
        inventory.validate_params(lead_time, service_level, on_hand)
    except inventory.ParameterError as exc:
        raise ApiError(str(exc), 400)

    run = forecast_runs.latest_run(product_id, with_samples=True)
    if run is None or run.get('samples') is None:
        raise ApiError('No forecast has been generated for this product yet. Generate a forecast first.', 404)

    as_of = datetime.fromisoformat(run['as_of_date']).date()
    rec = inventory.recommend(run['samples'], as_of, lead_time, service_level, on_hand)

    accuracy = evaluation_store.load_latest_evaluation(product_id)
    verdict = accuracy['test_folds']['1-7']['verdict'] if accuracy else None
    rec.update({
        'product_id': product_id,
        'run_id': run['run_id'],
        'as_of_date': run['as_of_date'],
        'stale': run['stale'],
        'stale_reason': run['stale_reason'],
        'verdict_1_7': verdict,
    })
    return jsonify(rec), 200


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()}), 200


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    app.run(host='0.0.0.0', port=Config.FLASK_PORT, debug=Config.DEBUG)
