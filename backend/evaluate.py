"""Offline evaluation job (ADR-0006).

    python -m evaluate --all [--workers N]
    python -m evaluate --product 3

Runs rolling CV, baselines and the regressor ablation, then stores an evaluation run (including the
selected configuration) per product. The API only reads these results.
"""
import argparse
import multiprocessing as mp
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import data
import evaluation as ev
import evaluation_store as store
from config import Config
from database import get_cursor, reset_pool
from holiday_frame import build_holidays_frame


def evaluate_product(product_id, uncertainty_samples=None, verbose=False, **cv_overrides):
    """Evaluate and persist one product. Returns a summary dict (never raises for thin history)."""
    t0 = time.time()
    with get_cursor() as cur:
        cur.execute('SELECT product_name FROM products WHERE product_id = %s', (product_id,))
        row = cur.fetchone()
        if row is None:
            return {'product_id': product_id, 'status': 'error', 'reason': 'product not found'}
        name = row['product_name']
        history = data.get_history(product_id, cur=cur)
        holidays_frame = build_holidays_frame(data.get_holidays_table(cur=cur))

    base = {'product_id': product_id, 'name': name}
    try:
        result = ev.evaluate_history(history, holidays_frame, uncertainty_samples=uncertainty_samples,
                                     progress=print if verbose else None, **cv_overrides)
    except ev.InsufficientHistory as exc:
        return {**base, 'status': 'skipped', 'reason': str(exc), 'required_days': exc.required_days,
                'history_days': int((history['ds'].max() - history['ds'].min()).days) if len(history) else 0}
    except ValueError as exc:   # e.g. fewer days of data than the horizon
        return {**base, 'status': 'skipped', 'reason': str(exc), 'required_days': ev.min_history_days(),
                'history_days': int((history['ds'].max() - history['ds'].min()).days) if len(history) else 0}

    eval_id = store.save_evaluation(product_id, result, data.history_fingerprint(history),
                                    Config.TRAINING_START_DATE)
    verdicts = {}
    snapshot = store.load_latest_evaluation(product_id)
    for label in ev.ALL_BUCKETS:
        verdicts[label] = snapshot['test_folds'][label]['verdict']
    return {**base, 'status': 'ok', 'eval_id': eval_id, 'selected_arm': result['selected_arm'],
            'verdicts': verdicts, 'seconds': round(time.time() - t0, 1)}


def _worker_init():
    reset_pool()      # never share a connection pool across processes


def _worker(args):
    product_id, samples = args
    try:
        return evaluate_product(product_id, samples)
    except Exception as exc:   # one bad product must not abort the batch
        return {'product_id': product_id, 'status': 'error', 'reason': f'{type(exc).__name__}: {exc}'}


def evaluate_all(product_ids, workers=None, uncertainty_samples=None):
    workers = workers or max(1, min(len(product_ids), (os.cpu_count() or 2) - 1))
    results = []
    if workers == 1:
        for pid in product_ids:
            results.append(_worker((pid, uncertainty_samples)))
            _print_result(results[-1])
        return results
    ctx = mp.get_context('spawn')
    with ProcessPoolExecutor(max_workers=workers, mp_context=ctx, initializer=_worker_init) as pool:
        futures = [pool.submit(_worker, (pid, uncertainty_samples)) for pid in product_ids]
        for fut in as_completed(futures):
            results.append(fut.result())
            _print_result(results[-1])
    return results


def _print_result(r):
    label = f"[{r['product_id']}] {r.get('name', '')}"
    if r['status'] == 'ok':
        v = ' '.join(f"{b}={r['verdicts'][b]}" for b in ev.BUCKET_LABELS)
        print(f"{label}: selected {r['selected_arm']} | {v} ({r['seconds']}s)", flush=True)
    elif r['status'] == 'skipped':
        print(f"{label}: SKIPPED - {r['reason']}; needs about {r['required_days']} days of history, "
              f"has {r.get('history_days', 0)}", flush=True)
    else:
        print(f"{label}: ERROR - {r['reason']}", flush=True)


def summarize(results):
    ok = [r for r in results if r['status'] == 'ok']
    print('\n=== Summary ===')
    print(f"evaluated {len(ok)}, skipped {sum(r['status'] == 'skipped' for r in results)}, "
          f"errors {sum(r['status'] == 'error' for r in results)}")
    for label in ev.BUCKET_LABELS:
        counts = {v: sum(1 for r in ok if r['verdicts'][label] == v) for v in ('beats', 'comparable', 'worse')}
        print(f"  bucket {label:>5}: {counts}")
    arms = {}
    for r in ok:
        arms[r['selected_arm']] = arms.get(r['selected_arm'], 0) + 1
    print(f"  selected configurations: {arms}")
    sl = store.pooled_service_level()
    if sl['n']:
        print(f"  pooled achieved service level: {sl['achieved']:.1%} ({sl['hits']}/{sl['n']} test folds) "
              f"vs target {sl['target']:.0%}")


def main(argv=None):
    parser = argparse.ArgumentParser(description='Run rolling-CV evaluation and store the results')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--all', action='store_true', help='evaluate every product')
    group.add_argument('--product', type=int, help='evaluate one product id')
    parser.add_argument('--workers', type=int, default=None, help='parallel processes (default: cores - 1)')
    parser.add_argument('--uncertainty-samples', type=int, default=None,
                        help='Prophet uncertainty samples (default from config)')
    args = parser.parse_args(argv)

    if args.product is not None:
        ids = [args.product]
    else:
        with get_cursor() as cur:
            cur.execute('SELECT product_id FROM products ORDER BY product_id')
            ids = [r['product_id'] for r in cur.fetchall()]
    if not ids:
        print('No products found. Load data first (generate_sample_data.py or import_kaggle_store_sales.py).')
        return 1
    results = evaluate_all(ids, args.workers, args.uncertainty_samples)
    summarize(results)
    return 0 if all(r['status'] != 'error' for r in results) else 2


if __name__ == '__main__':
    sys.exit(main())
