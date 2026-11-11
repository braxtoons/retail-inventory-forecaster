"""Production forecast runs: generate, persist, read, staleness (ADR-0010).

Reads never train: `latest_run` only reads stored rows and compares configuration and data
fingerprint to flag a run as stale.
"""
import logging

import numpy as np
import pandas as pd
from psycopg2.extras import Json, execute_values

import data
import model as model_mod
from config import Config
from database import get_cursor
from holiday_frame import build_holidays_frame

log = logging.getLogger(__name__)


class InsufficientData(ValueError):
    pass


def get_selected_config(product_id, cur=None):
    """The latest evaluation's selected configuration, or None when the product is not evaluated."""
    sql = "SELECT selected_config FROM evaluation_runs WHERE product_id = %s ORDER BY eval_id DESC LIMIT 1"
    if cur is None:
        with get_cursor() as c:
            c.execute(sql, (product_id,))
            row = c.fetchone()
    else:
        cur.execute(sql, (product_id,))
        row = cur.fetchone()
    return model_mod.normalize_config(row['selected_config']) if row else None


def resolve_config(product_id, cur=None):
    """(config, config_source) used for a new production forecast."""
    selected = get_selected_config(product_id, cur)
    if selected is None:
        return dict(model_mod.DEFAULT_CONFIG), 'default'
    return selected, 'selected'


def generate_run(product_id, seed=None):
    """Train once with the current configuration and store a 90-day run atomically."""
    seed = Config.FORECAST_SEED if seed is None else seed
    horizon = Config.MAX_FORECAST_DAYS

    with get_cursor() as cur:
        cur.execute('SELECT 1 FROM products WHERE product_id = %s', (product_id,))
        if cur.fetchone() is None:
            raise LookupError(f'product {product_id} not found')
        history = data.get_history(product_id, cur=cur)
        planned = data.get_planned_promotions(product_id, cur=cur)
        holidays_frame = build_holidays_frame(data.get_holidays_table(cur=cur))
        config, source = resolve_config(product_id, cur)
        fingerprint = data.history_fingerprint(history)

    if len(history) < 10:
        raise InsufficientData(f'Insufficient data for product {product_id}')

    as_of = history['ds'].max()
    future = model_mod.build_future_frame(history, horizon, as_of, planned)
    forecast, fitted = model_mod.fit_predict(config, history, future, holidays_frame, seed=seed)
    paths = model_mod.cumulative_sample_paths(fitted, future, seed)

    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO forecast_runs (product_id, as_of_date, config, config_source, seed,
                                          promo_known_through, data_fingerprint)
               VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING run_id""",
            (product_id, as_of.date(), Json(config), source, seed, data.promo_known_through(planned), fingerprint))
        run_id = cur.fetchone()['run_id']
        rows = [(run_id, product_id, ds.date(), max(0.0, float(y)), max(0.0, float(lo)), max(0.0, float(hi)))
                for ds, y, lo, hi in zip(forecast['ds'], forecast['yhat'], forecast['yhat_lower'],
                                         forecast['yhat_upper'])]
        execute_values(cur, """INSERT INTO forecasts (run_id, product_id, forecast_date, predicted_quantity,
                                                       lower_bound, upper_bound) VALUES %s""", rows)
        cur.execute('INSERT INTO forecast_run_samples (run_id, cumulative_paths) VALUES (%s, %s)',
                    (run_id, paths.astype(np.float32).tolist()))
        prune_runs(cur, product_id)
    return latest_run(product_id)


def prune_runs(cur, product_id, keep=None):
    keep = Config.KEEP_FORECAST_RUNS if keep is None else keep
    cur.execute(
        """DELETE FROM forecast_runs WHERE product_id = %s AND run_id NOT IN (
               SELECT run_id FROM forecast_runs WHERE product_id = %s ORDER BY run_id DESC LIMIT %s)""",
        (product_id, product_id, keep))


def _iso(d):
    return d.isoformat() if d is not None else None


def latest_run(product_id, with_samples=False):
    """The newest stored run with its daily rows and staleness, or None. Never trains."""
    with get_cursor() as cur:
        cur.execute('SELECT * FROM forecast_runs WHERE product_id = %s ORDER BY run_id DESC LIMIT 1',
                    (product_id,))
        run = cur.fetchone()
        if run is None:
            return None
        cur.execute("""SELECT forecast_date, predicted_quantity::float8 AS predicted_quantity,
                              lower_bound::float8 AS lower_bound, upper_bound::float8 AS upper_bound
                       FROM forecasts WHERE run_id = %s ORDER BY forecast_date""", (run['run_id'],))
        days = cur.fetchall()
        samples = None
        if with_samples:
            cur.execute('SELECT cumulative_paths FROM forecast_run_samples WHERE run_id = %s', (run['run_id'],))
            row = cur.fetchone()
            samples = np.asarray(row['cumulative_paths'], dtype=float) if row else None
        current_config, _ = resolve_config(product_id, cur)
        fingerprint = data.get_fingerprint(product_id, cur=cur)

    stale, reason = staleness(run['config'], run['data_fingerprint'], current_config, fingerprint)
    out = {
        'run_id': run['run_id'],
        'product_id': product_id,
        'created_at': _iso(run['created_at']),
        'as_of_date': _iso(run['as_of_date']),
        'config': model_mod.normalize_config(run['config']),
        'config_source': run['config_source'],
        'promo_known_through': _iso(run['promo_known_through']),
        'seed': run['seed'],
        'stale': stale,
        'stale_reason': reason,
        'days': days,
    }
    if with_samples:
        out['samples'] = samples
    return out


def staleness(run_config, run_fingerprint, current_config, current_fingerprint):
    """(stale?, reason) for a stored run vs. the current configuration and data."""
    if model_mod.normalize_config(run_config) != model_mod.normalize_config(current_config):
        return True, 'configuration changed since this forecast was generated'
    if run_fingerprint != current_fingerprint:
        return True, 'data changed since this forecast was generated'
    return False, None
