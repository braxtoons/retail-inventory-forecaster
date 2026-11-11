"""API integration tests (db tier). Prophet is replaced by a fake behind the build_model seam."""
import json

import numpy as np
import pandas as pd
import pytest
from psycopg2.extras import Json

import evaluate
import forecast_runs
import model as model_mod
from generate_sample_data import generate, write_to_db

pytestmark = pytest.mark.db


class FakeModel:
    """Minimal stand-in with Prophet's fit / predict / predictive_samples surface."""
    fits = 0

    def __init__(self, config, n_samples):
        self.config, self.n_samples = config, n_samples

    def fit(self, df):
        FakeModel.fits += 1
        self.level = float(df['y'].tail(28).mean())
        self.sd = float(df['y'].tail(28).std() or 1.0)

    def predict(self, future):
        out = pd.DataFrame({'ds': future['ds'], 'yhat': self.level})
        out['yhat_lower'] = self.level - 1.96 * self.sd
        out['yhat_upper'] = self.level + 1.96 * self.sd
        return out

    def predictive_samples(self, future):
        n = len(future)
        return {'yhat': self.level + self.sd * np.random.standard_normal((n, self.n_samples))}


@pytest.fixture()
def client(db, monkeypatch):
    write_to_db(generate())
    FakeModel.fits = 0
    monkeypatch.setattr(model_mod, 'build_model',
                        lambda config, holidays_frame=None, uncertainty_samples=None:
                        FakeModel(config, uncertainty_samples or 200))
    import app as app_module
    app_module.app.config['TESTING'] = True
    return app_module.app.test_client()


def post_forecast(client, **body):
    return client.post('/api/forecast', data=json.dumps(body), content_type='application/json')


def test_products_and_historical(client):
    products = client.get('/api/products').get_json()
    assert len(products) == 4 and {'product_id', 'product_name'} <= set(products[0])
    hist = client.get('/api/historical?product_id=1&days_back=30').get_json()
    assert 25 <= len(hist) <= 31 and isinstance(hist[0]['quantity_sold'], float)
    assert client.get('/api/historical').status_code == 400
    assert client.get('/api/historical?product_id=1&days_back=abc').status_code == 400


@pytest.mark.parametrize('days', [0, 91, -5, 'x', 7.5, True])
def test_invalid_forecast_days(client, days):
    assert post_forecast(client, product_id=1, forecast_days=days).status_code == 400


def test_forecast_validation_and_errors(client):
    assert post_forecast(client).status_code == 400
    assert post_forecast(client, product_id='abc').status_code == 400
    assert client.post('/api/forecast', data='not json', content_type='application/json').status_code == 400
    assert post_forecast(client, product_id=999).status_code == 404


def test_generate_forecast_returns_run_metadata(client):
    r = post_forecast(client, product_id=1, forecast_days=14)
    assert r.status_code == 200
    body = r.get_json()
    assert body['config_source'] == 'default' and body['config'] == {'holidays': True, 'promo': False, 'oil': False}
    assert body['as_of_date'] == '2024-12-31' and body['stale'] is False and body['stale_reason'] is None
    assert body['promo_known_through'] == '2025-01-30'
    assert body['run_id'] and body['created_at']
    assert len(body['forecast']) == 14
    day = body['forecast'][0]
    assert day['forecast_date'] == '2025-01-01'
    assert {'predicted_quantity', 'lower_bound', 'upper_bound', 'seasonal_naive'} <= set(day)
    assert day['seasonal_naive'] is not None


def test_run_always_stores_full_horizon_and_samples(client, db):
    post_forecast(client, product_id=1, forecast_days=7)
    with db.get_cursor() as cur:
        cur.execute('SELECT COUNT(*) AS n FROM forecasts')
        assert cur.fetchone()['n'] == 90
        cur.execute('SELECT cumulative_paths FROM forecast_run_samples')
        paths = np.asarray(cur.fetchone()['cumulative_paths'])
    assert paths.shape == (200, 90) and (np.diff(paths, axis=1) >= 0).all()      # cumulative, clipped at 0


def test_cached_read_does_not_train_and_trims(client):
    assert client.get('/api/forecast/1').status_code == 404
    post_forecast(client, product_id=1, forecast_days=30)
    fits = FakeModel.fits
    for days in (1, 30, 90):
        body = client.get(f'/api/forecast/1?forecast_days={days}').get_json()
        assert len(body['forecast']) == days
    assert client.get('/api/forecast/1').get_json()['forecast_days'] == 90
    assert client.get('/api/forecast/1?forecast_days=91').status_code == 400
    assert FakeModel.fits == fits                                                  # reads never train


def test_only_latest_five_runs_kept(client, db):
    for _ in range(7):
        post_forecast(client, product_id=1)
    with db.get_cursor() as cur:
        cur.execute('SELECT COUNT(*) AS n FROM forecast_runs WHERE product_id = 1')
        assert cur.fetchone()['n'] == 5
        cur.execute('SELECT COUNT(*) AS n FROM forecasts')
        assert cur.fetchone()['n'] == 5 * 90                                       # cascade removed pruned rows


def test_stale_when_configuration_changes(client, db):
    post_forecast(client, product_id=1)
    with db.get_cursor() as cur:
        cur.execute("""INSERT INTO evaluation_runs (product_id, cv_params, data_fingerprint, selected_config)
                       VALUES (1, %s, 'x', %s)""", (Json({}), Json({'holidays': True, 'promo': True, 'oil': False})))
    body = client.get('/api/forecast/1').get_json()
    assert body['stale'] is True and 'configuration' in body['stale_reason']
    # regenerating adopts the selected configuration and clears the flag
    regen = post_forecast(client, product_id=1).get_json()
    assert regen['config_source'] == 'selected' and regen['config']['promo'] is True and regen['stale'] is False


def test_stale_when_data_changes(client, db):
    post_forecast(client, product_id=1)
    with db.get_cursor() as cur:
        cur.execute("INSERT INTO sales_data (product_id, sale_date, quantity_sold, total_amount, on_promotion) "
                    "VALUES (1, '2025-01-01', 100, 399, 0)")
    body = client.get('/api/forecast/1').get_json()
    assert body['stale'] is True and 'data' in body['stale_reason']


def test_accuracy_not_evaluated_names_command(client):
    r = client.get('/api/accuracy/1')
    assert r.status_code == 404 and 'python -m evaluate' in r.get_json()['error']


def test_accuracy_after_evaluation(client):
    summary = evaluate.evaluate_product(1, 100, period=90)
    assert summary['status'] == 'ok', summary
    body = client.get('/api/accuracy/1').get_json()
    assert set(body['test_folds']) == {'1-7', '8-30', '31-90', 'all'}
    bucket = body['test_folds']['all']
    assert set(bucket['models']) == {'prophet', 'naive', 'seasonal_naive'}
    assert len(bucket['per_fold']) == 3 and bucket['verdict'] in ('beats', 'comparable', 'worse')
    assert body['ablation']['label'] == 'selection folds' and len(body['ablation']['arms']) == 5
    assert body['service_level']['target'] == pytest.approx(0.95) and body['service_level']['folds'] == 3
    assert body['selected_config'] and body['evaluated_at']


def test_evaluate_skips_thin_history(client, db):
    with db.get_cursor() as cur:
        cur.execute("INSERT INTO products (product_name) VALUES ('THIN') RETURNING product_id")
        pid = cur.fetchone()['product_id']
        cur.execute("INSERT INTO sales_data (product_id, sale_date, quantity_sold) "
                    "SELECT %s, d::date, 5 FROM generate_series('2024-01-01'::date, '2024-06-30', '1 day') d", (pid,))
    summary = evaluate.evaluate_product(pid, 100)
    assert summary['status'] == 'skipped' and summary['required_days'] == 815


def test_inventory_requires_forecast_run(client):
    r = client.get('/api/inventory/1')
    assert r.status_code == 404 and 'forecast' in r.get_json()['error'].lower()


def test_inventory_recommendation(client):
    post_forecast(client, product_id=1)
    fits = FakeModel.fits
    body = client.get('/api/inventory/1').get_json()
    assert body['lead_time'] == 7 and body['service_level'] == 0.95
    assert body['reorder_point'] > body['mean_lead_time_demand'] > 0 and body['safety_stock'] > 0
    assert body['assumptions'] and body['verdict_1_7'] is None and 'risk_level' not in body

    rop = body['reorder_point']
    body = client.get(f'/api/inventory/1?on_hand={rop}&lead_time=7&service_level=0.95').get_json()
    assert body['risk_level'] == 'ok' and body['reorder_now'] is True
    body = client.get('/api/inventory/1?on_hand=0').get_json()
    assert body['risk_level'] == 'high' and body['projected_stock_out_date'] == '2025-01-01'
    body = client.get('/api/inventory/1?on_hand=1000000000').get_json()
    assert body['beyond_horizon'] is True and body['projected_stock_out_date'] is None
    assert FakeModel.fits == fits                                                  # no training on read


def test_inventory_includes_baseline_verdict_when_evaluated(client):
    evaluate.evaluate_product(1, 100, period=90)
    post_forecast(client, product_id=1)
    assert client.get('/api/inventory/1').get_json()['verdict_1_7'] in ('beats', 'comparable', 'worse')


@pytest.mark.parametrize('query', ['lead_time=0', 'lead_time=-1', 'lead_time=91', 'lead_time=7.5', 'lead_time=abc',
                                   'service_level=0.5', 'service_level=0.999', 'service_level=2', 'service_level=x',
                                   'on_hand=-1', 'on_hand=abc'])
def test_inventory_validation(client, query):
    post_forecast(client, product_id=1)
    r = client.get(f'/api/inventory/1?{query}')
    assert r.status_code == 400 and r.get_json()['error']


def test_unexpected_error_is_generic(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError('secret connection string postgres://user:pw@host')
    monkeypatch.setattr(forecast_runs, 'latest_run', boom)
    client.application.config['PROPAGATE_EXCEPTIONS'] = False
    r = client.get('/api/forecast/1')
    assert r.status_code == 500
    assert r.get_json() == {'error': 'Internal server error'}
    assert 'secret' not in r.get_data(as_text=True)
