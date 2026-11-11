"""Persist and read evaluation runs (ADR-0010). The API only ever reads."""
from psycopg2.extras import Json, execute_values

import data
import evaluation as ev
import model as model_mod
from database import get_cursor

METRIC_COLS = ('mae', 'rmse', 'wape', 'mape', 'mape_excluded', 'coverage', 'n')


def _rows(eval_id, model, arm, fold_set, cutoff, metrics_by_bucket):
    rows = []
    for bucket in ev.ALL_BUCKETS:
        m = metrics_by_bucket.get(bucket)
        if m is None:
            continue
        rows.append((eval_id, model, arm, cutoff, fold_set, bucket) + tuple(m[c] for c in METRIC_COLS))
    return rows


def save_evaluation(product_id, result, fingerprint, training_start):
    """Insert one evaluation run with all metric and calibration rows in a single transaction."""
    selected = result['selected_arm']
    with get_cursor() as cur:
        cur.execute(
            """INSERT INTO evaluation_runs (product_id, cv_params, training_start, data_fingerprint, selected_config)
               VALUES (%s, %s, %s, %s, %s) RETURNING eval_id""",
            (product_id, Json(result['cv_params']), training_start, fingerprint, Json(result['selected_config'])))
        eval_id = cur.fetchone()['eval_id']

        rows = []
        # Selection folds: every ablation arm, labelled fold_set='selection'
        for arm, frames in result['selection_frames'].items():
            for cutoff, frame in frames.items():
                rows += _rows(eval_id, 'prophet', arm, 'selection', cutoff.date(), ev.bucket_metrics(frame))
            rows += _rows(eval_id, 'prophet', arm, 'selection', None, ev.pooled_bucket_metrics(list(frames.values())))
        # Test folds: Prophet (selected arm) and both baselines on identical folds
        for model, frames in result['test_frames'].items():
            arm = selected if model == 'prophet' else None
            for cutoff, frame in zip(result['test_cutoffs'], frames):
                rows += _rows(eval_id, model, arm, 'test', cutoff.date(), ev.bucket_metrics(frame))
            rows += _rows(eval_id, model, arm, 'test', None, ev.pooled_bucket_metrics(frames))
        execute_values(cur, """INSERT INTO evaluation_metrics (eval_id, model, arm, fold_cutoff, fold_set,
                               horizon_bucket, mae, rmse, wape, mape, mape_excluded, coverage, n) VALUES %s""", rows)

        execute_values(cur, "INSERT INTO evaluation_service_level (eval_id, fold_cutoff, lead_time, alpha, hit) VALUES %s",
                       [(eval_id, c['fold_cutoff'].date(), c['lead_time'], c['alpha'], c['hit'])
                        for c in result['calibration']])
    return eval_id


def _metrics(row):
    return {c: row[c] for c in METRIC_COLS}


def load_latest_evaluation(product_id):
    """The accuracy response for a product, or None when it has never been evaluated."""
    with get_cursor() as cur:
        cur.execute('SELECT * FROM evaluation_runs WHERE product_id = %s ORDER BY eval_id DESC LIMIT 1', (product_id,))
        run = cur.fetchone()
        if run is None:
            return None
        cur.execute('SELECT * FROM evaluation_metrics WHERE eval_id = %s', (run['eval_id'],))
        metric_rows = cur.fetchall()
        cur.execute('SELECT fold_cutoff, lead_time, alpha::float8 AS alpha, hit FROM evaluation_service_level '
                    'WHERE eval_id = %s ORDER BY fold_cutoff', (run['eval_id'],))
        sl_rows = cur.fetchall()
        current_fp = data.get_fingerprint(product_id, run['training_start'], cur=cur)

    params = run['cv_params']
    selected_config = model_mod.normalize_config(run['selected_config'])
    selected_arm = model_mod.arm_name(selected_config)

    # ---- test folds
    test = [r for r in metric_rows if r['fold_set'] == 'test']
    buckets = {}
    for label in ev.ALL_BUCKETS:
        entry = {'models': {}, 'per_fold': []}
        for model in ('prophet',) + ev.BASELINES:
            pooled = [r for r in test if r['model'] == model and r['horizon_bucket'] == label and r['fold_cutoff'] is None]
            if pooled:
                entry['models'][model] = _metrics(pooled[0])
        folds = sorted({r['fold_cutoff'] for r in test if r['fold_cutoff'] is not None})
        wins = losses = 0
        for cutoff in folds:
            fold = {'fold_cutoff': cutoff.isoformat()}
            for model in ('prophet',) + ev.BASELINES:
                r = [x for x in test if x['model'] == model and x['horizon_bucket'] == label and x['fold_cutoff'] == cutoff]
                fold[model] = _metrics(r[0]) if r else None
            p, s = (fold['prophet'] or {}).get('wape'), (fold['seasonal_naive'] or {}).get('wape')
            if p is not None and s is not None:
                wins += p < s
                losses += p > s
            entry['per_fold'].append(fold)
        prophet_w = entry['models'].get('prophet', {}).get('wape')
        snaive_w = entry['models'].get('seasonal_naive', {}).get('wape')
        entry['skill'] = ev.skill(prophet_w, snaive_w)
        entry['fold_wins'], entry['fold_losses'], entry['n_folds'] = int(wins), int(losses), len(folds)
        entry['verdict'] = ev.verdict(entry['skill'], wins, losses, len(folds),
                                      params.get('verdict_skill_threshold'), params.get('verdict_min_fold_share'))
        buckets[label] = entry

    # ---- ablation (selection folds)
    ablation = []
    for arm, cfg in model_mod.ARMS.items():
        rows = [r for r in metric_rows if r['fold_set'] == 'selection' and r['arm'] == arm
                and r['horizon_bucket'] == 'all']
        if not rows:
            continue
        pooled = [r for r in rows if r['fold_cutoff'] is None]
        ablation.append({
            'arm': arm, 'config': cfg, 'selected': arm == selected_arm,
            'wape': pooled[0]['wape'] if pooled else None,
            'mae': pooled[0]['mae'] if pooled else None,
            'per_fold_wape': [r['wape'] for r in sorted((x for x in rows if x['fold_cutoff'] is not None),
                                                        key=lambda x: x['fold_cutoff'])],
        })

    hits = sum(1 for r in sl_rows if r['hit'])
    service_level = {
        'target': sl_rows[0]['alpha'] if sl_rows else None,
        'lead_time': sl_rows[0]['lead_time'] if sl_rows else None,
        'achieved': hits / len(sl_rows) if sl_rows else None,
        'folds': len(sl_rows),
        'hits': hits,
        'per_fold': [{'fold_cutoff': r['fold_cutoff'].isoformat(), 'hit': r['hit']} for r in sl_rows],
    }
    return {
        'product_id': product_id,
        'evaluated_at': run['created_at'].isoformat(),
        'training_start': run['training_start'].isoformat() if run['training_start'] else None,
        'cv_params': params,
        'selected_config': selected_config,
        'selected_arm': selected_arm,
        'data_changed': current_fp != run['data_fingerprint'],
        'test_folds': buckets,
        'ablation': {'label': 'selection folds', 'arms': ablation},
        'service_level': service_level,
    }


def pooled_service_level():
    """Achieved cycle service level pooled over each product's latest evaluation."""
    with get_cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) AS n, COALESCE(SUM(CASE WHEN s.hit THEN 1 ELSE 0 END), 0) AS hits,
                   MIN(s.alpha)::float8 AS target
            FROM evaluation_service_level s
            JOIN evaluation_runs r ON r.eval_id = s.eval_id
            WHERE r.eval_id = (SELECT MAX(eval_id) FROM evaluation_runs WHERE product_id = r.product_id)""")
        row = cur.fetchone()
    n = int(row['n'])
    return {'n': n, 'hits': int(row['hits']), 'achieved': row['hits'] / n if n else None, 'target': row['target']}
