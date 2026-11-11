"""Slow tier: real Prophet on the seeded synthetic dataset with a reduced configuration
(uncertainty_samples=200, 90-day fold period). Asserts ADR-0011 ground truth."""
import pytest

import evaluate
import evaluation as ev
import evaluation_store as store
import forecast_runs
from config import Config
from generate_sample_data import generate, write_to_db

pytestmark = [pytest.mark.slow, pytest.mark.db]

SAMPLES = 200
PERIOD = 90


@pytest.fixture(scope='module')
def evaluated(db_schema):
    import database
    with database.get_cursor() as cur:
        cur.execute('TRUNCATE forecast_run_samples, forecasts, forecast_runs, evaluation_service_level, '
                    'evaluation_metrics, evaluation_runs, planned_promotions, sales_data, oil_prices, '
                    'holidays, products RESTART IDENTITY CASCADE')
    write_to_db(generate())
    summaries = {pid: evaluate.evaluate_product(pid, SAMPLES, period=PERIOD) for pid in (1, 2, 3, 4)}
    return summaries


def test_all_products_evaluated(evaluated):
    assert all(s['status'] == 'ok' for s in evaluated.values()), evaluated


def test_ablation_selects_promo_and_excludes_oil(evaluated):
    for pid, s in evaluated.items():
        acc = store.load_latest_evaluation(pid)
        cfg = acc['selected_config']
        assert cfg['promo'] is True, (pid, acc['selected_arm'])
        assert cfg['oil'] is False, (pid, acc['selected_arm'])
        assert acc['ablation']['label'] == 'selection folds'
        assert {a['arm'] for a in acc['ablation']['arms']} == set(ev.model_mod.ARMS)


def test_accuracy_structure_and_beats_baseline(evaluated):
    acc = store.load_latest_evaluation(1)
    assert acc['cv_params']['n_test_folds'] == 3
    bucket = acc['test_folds']['all']
    assert bucket['n_folds'] == 3 and len(bucket['per_fold']) == 3
    assert set(bucket['models']) == {'prophet', 'naive', 'seasonal_naive'}
    assert bucket['skill'] > 0.05 and bucket['verdict'] == 'beats'    # promo-aware model vs. seasonal-naive
    assert 0 <= bucket['models']['prophet']['coverage'] <= 1
    assert set(acc['test_folds']) == {'1-7', '8-30', '31-90', 'all'}


def test_achieved_service_level_near_target(evaluated):
    sl = store.pooled_service_level()
    assert sl['n'] == 12 and sl['target'] == pytest.approx(0.95)
    # 12 test folds is a coarse estimate; Prophet intervals are known to run narrow, so allow slack
    assert sl['achieved'] >= 0.75


def test_forecast_run_uses_selected_config_and_is_not_stale(evaluated, monkeypatch):
    monkeypatch.setattr(Config, 'UNCERTAINTY_SAMPLES', SAMPLES)
    run = forecast_runs.generate_run(1)
    assert run['config_source'] == 'selected' and run['config']['promo'] is True
    assert len(run['days']) == 90 and run['stale'] is False
    assert run['promo_known_through'] is not None
