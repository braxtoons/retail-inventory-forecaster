"""Rolling-origin cross-validation, baselines, metrics, ablation, verdicts, calibration.

Rolling CV is a custom loop (not `prophet.diagnostics.cross_validation`) because the stock
function feeds *actual* future regressor values to the model. Here every fold fits
`model.build_model(config)` and predicts on `model.build_future_frame(as_of=cutoff)`, the same
two functions production uses (ADR-0002).
"""
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from prophet.diagnostics import generate_cutoffs

import model as model_mod
from config import Config

BUCKET_LABELS = [f'{lo}-{hi}' for lo, hi in Config.HORIZON_BUCKETS]
ALL_BUCKETS = BUCKET_LABELS + ['all']
BASELINES = ('naive', 'seasonal_naive')


class InsufficientHistory(ValueError):
    """Raised when a product cannot yield the required selection and test folds."""

    def __init__(self, message, required_days=None):
        super().__init__(message)
        self.required_days = required_days


# --------------------------------------------------------------------------- folds

def min_history_days(initial=None, horizon=None, period=None, n_test=None, n_selection=None):
    """Days of history needed for `n_test` test folds plus `n_selection` selection folds."""
    initial = initial or Config.CV_INITIAL_DAYS
    horizon = horizon or Config.MAX_FORECAST_DAYS
    period = period or Config.CV_PERIOD_DAYS
    n_test = n_test or Config.N_TEST_FOLDS
    n_selection = n_selection or Config.MIN_SELECTION_FOLDS
    dropped = max(0, math.ceil(horizon / period) - 1)      # folds whose window overlaps the test period
    n_cutoffs = n_test + dropped + n_selection
    return int(initial + horizon + (n_cutoffs - 1) * period)


def make_cutoffs(history, horizon=None, initial=None, period=None):
    horizon = horizon or Config.MAX_FORECAST_DAYS
    initial = initial or Config.CV_INITIAL_DAYS
    period = period or Config.CV_PERIOD_DAYS
    return generate_cutoffs(history, pd.Timedelta(days=horizon), pd.Timedelta(days=initial),
                            pd.Timedelta(days=period))


def split_folds(cutoffs, horizon=None, n_test=None, min_selection=None):
    """Last `n_test` cutoffs are test folds; earlier cutoffs whose window ends on or before the
    first test cutoff are selection folds; folds overlapping the test period are dropped."""
    horizon = horizon or Config.MAX_FORECAST_DAYS
    n_test = n_test or Config.N_TEST_FOLDS
    min_selection = Config.MIN_SELECTION_FOLDS if min_selection is None else min_selection
    cutoffs = sorted(pd.Timestamp(c) for c in cutoffs)
    test = cutoffs[-n_test:] if len(cutoffs) >= n_test else []
    if len(test) < n_test:
        raise InsufficientHistory(f'need {n_test} test folds, history yields {len(cutoffs)} cutoffs',
                                  min_history_days())
    first_test = test[0]
    selection = [c for c in cutoffs[:-n_test] if c + pd.Timedelta(days=horizon) <= first_test]
    if len(selection) < min_selection:
        raise InsufficientHistory(
            f'need {min_selection} selection folds, history yields {len(selection)}', min_history_days())
    return selection, test


# --------------------------------------------------------------------------- baselines

def naive_forecast(train, cutoff, horizon):
    """Repeat the last observed value."""
    last = float(train.loc[train['ds'] <= cutoff, 'y'].iloc[-1])
    return np.full(int(horizon), last)


def seasonal_naive_forecast(train, cutoff, horizon):
    """Repeat the last observed week: day h takes the value 7 days before the matching weekday in the
    last week. A missing lag date (closure) falls back to the most recent prior observation."""
    cutoff = pd.Timestamp(cutoff)
    series = train[train['ds'] <= cutoff].set_index('ds')['y']
    h = np.arange(1, int(horizon) + 1)
    lag_dates = [cutoff + pd.Timedelta(days=int(((k - 1) % 7) + 1 - 7)) for k in h]
    values = series.reindex(pd.DatetimeIndex(lag_dates), method='ffill')
    return values.bfill().to_numpy(dtype=float)


# --------------------------------------------------------------------------- metrics

def bucket_mask(h, label):
    if label == 'all':
        return np.ones(len(h), dtype=bool)
    lo, hi = (int(x) for x in label.split('-'))
    return (h >= lo) & (h <= hi)


def compute_metrics(actual, pred, lower=None, upper=None):
    """MAE, RMSE, WAPE, zero-safe MAPE (percent, with excluded count) and interval coverage."""
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    n = len(actual)
    if n == 0:
        return dict(mae=None, rmse=None, wape=None, mape=None, mape_excluded=0, coverage=None, n=0,
                    abs_err=0.0, actual_sum=0.0)
    err = np.abs(actual - pred)
    total = float(actual.sum())
    nonzero = actual != 0
    coverage = None
    if lower is not None and upper is not None:
        coverage = float(np.mean((actual >= np.asarray(lower)) & (actual <= np.asarray(upper))))
    return dict(
        mae=float(err.mean()),
        rmse=float(np.sqrt(np.mean((actual - pred) ** 2))),
        wape=float(err.sum() / total) if total > 0 else None,
        mape=float(np.mean(err[nonzero] / np.abs(actual[nonzero])) * 100) if nonzero.any() else None,
        mape_excluded=int((~nonzero).sum()),
        coverage=coverage,
        n=n,
        abs_err=float(err.sum()),
        actual_sum=total,
    )


def skill(wape_model, wape_baseline):
    """1 - WAPE_model / WAPE_baseline; None when undefined."""
    if wape_model is None or not wape_baseline:
        return None
    return 1.0 - wape_model / wape_baseline


def verdict(skill_value, wins, losses, n_folds, skill_threshold=None, min_fold_share=None):
    """`beats` / `worse` / `comparable` vs. seasonal-naive (ADR-0012)."""
    skill_threshold = Config.VERDICT_SKILL_THRESHOLD if skill_threshold is None else skill_threshold
    min_fold_share = Config.VERDICT_MIN_FOLD_SHARE if min_fold_share is None else min_fold_share
    if skill_value is None or n_folds == 0:
        return 'comparable'
    need = min_fold_share * n_folds - 1e-9
    if skill_value >= skill_threshold and wins >= need:
        return 'beats'
    if skill_value <= -skill_threshold and losses >= need:
        return 'worse'
    return 'comparable'


# --------------------------------------------------------------------------- ablation

def _pooled(folds):
    err = sum(e for e, _ in folds)
    act = sum(a for _, a in folds)
    return err / act if act > 0 else math.inf


def _fold_wape(e, a):
    return e / a if a > 0 else math.inf


def select_arm(scores, min_rel_gain=None, min_fold_win_share=None):
    """Greedy ablation from holidays-only (ADR-0007).

    `scores[arm]` is a list of `(abs_err_sum, actual_sum)` per selection fold, same fold order for
    every arm. A move to an adjacent arm (add one regressor, or drop holidays) is accepted only if it
    lowers pooled WAPE by at least `min_rel_gain` (relative) AND wins in at least `min_fold_win_share`
    of folds. Returns (selected arm, decision log).
    """
    min_rel_gain = Config.ABLATION_MIN_REL_GAIN if min_rel_gain is None else min_rel_gain
    share = Config.ABLATION_MIN_FOLD_WIN_SHARE if min_fold_win_share is None else min_fold_win_share
    arms = model_mod.ARMS
    current = 'holidays'
    log = []
    while True:
        cur_cfg = arms[current]
        best = None
        for cand, cfg in arms.items():
            if cand == current or cand not in scores or current not in scores:
                continue
            diff = [k for k in cfg if cfg[k] != cur_cfg[k]]
            removes_regressor = any(cur_cfg[k] and not cfg[k] for k in ('promo', 'oil'))
            if len(diff) != 1 or removes_regressor:
                continue
            base_w, cand_w = _pooled(scores[current]), _pooled(scores[cand])
            gain = (base_w - cand_w) / base_w if math.isfinite(base_w) and base_w > 0 else 0.0
            n = len(scores[cand])
            wins = sum(_fold_wape(*c) < _fold_wape(*b) for c, b in zip(scores[cand], scores[current]))
            ok = gain >= min_rel_gain and n > 0 and wins >= share * n - 1e-9
            log.append({'from': current, 'candidate': cand, 'rel_gain': gain, 'fold_wins': int(wins),
                        'n_folds': n, 'accepted': bool(ok)})
            if ok and (best is None or cand_w < best[1]):
                best = (cand, cand_w)
        if best is None:
            return current, log
        current = best[0]


# --------------------------------------------------------------------------- rolling loop

@dataclass
class FoldPrediction:
    cutoff: pd.Timestamp
    frame: pd.DataFrame            # h, ds, actual, yhat, yhat_lower, yhat_upper (rows with actuals only)
    cumulative_paths: np.ndarray = None   # (n_samples, horizon), when requested


def planned_from_actuals(history):
    """In CV, actual historical promotions stand in for planned promotions (ADR-0002)."""
    return history.set_index('ds')['on_promotion']


def run_fold(config, history, cutoff, horizon, holidays_frame, planned, uncertainty_samples=None,
             with_samples=False, seed=None):
    """Fit on history up to `cutoff`, predict the next `horizon` days, align with actuals."""
    cutoff = pd.Timestamp(cutoff)
    train = history[history['ds'] <= cutoff]
    future = model_mod.build_future_frame(train, horizon, cutoff, planned)
    forecast, fitted = model_mod.fit_predict(config, train, future, holidays_frame, uncertainty_samples, seed)
    paths = model_mod.cumulative_sample_paths(fitted, future, seed or Config.FORECAST_SEED) if with_samples else None

    out = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
    out['h'] = np.arange(1, len(out) + 1)
    for col in ('yhat', 'yhat_lower', 'yhat_upper'):
        out[col] = out[col].clip(lower=0.0)
    actual = history.set_index('ds')['y']
    out['actual'] = actual.reindex(out['ds']).to_numpy()
    out = out.dropna(subset=['actual']).reset_index(drop=True)   # closure days are never scored
    return FoldPrediction(cutoff, out, paths)


def baseline_fold(history, cutoff, horizon):
    """Naive and seasonal-naive predictions on the same fold rows as Prophet."""
    cutoff = pd.Timestamp(cutoff)
    train = history[history['ds'] <= cutoff]
    ds = pd.date_range(cutoff + pd.Timedelta(days=1), periods=horizon, freq='D')
    actual = history.set_index('ds')['y'].reindex(ds)
    h = np.arange(1, horizon + 1)
    keep = actual.notna().to_numpy()
    return {
        'naive': pd.DataFrame({'h': h[keep], 'actual': actual.to_numpy()[keep],
                               'yhat': naive_forecast(train, cutoff, horizon)[keep]}),
        'seasonal_naive': pd.DataFrame({'h': h[keep], 'actual': actual.to_numpy()[keep],
                                        'yhat': seasonal_naive_forecast(train, cutoff, horizon)[keep]}),
    }


def bucket_metrics(frame):
    """{bucket: metrics} for a fold frame with h, actual, yhat[, yhat_lower, yhat_upper]."""
    out = {}
    has_interval = 'yhat_lower' in frame
    for label in ALL_BUCKETS:
        sub = frame[bucket_mask(frame['h'].to_numpy(), label)]
        out[label] = compute_metrics(sub['actual'], sub['yhat'],
                                     sub['yhat_lower'] if has_interval else None,
                                     sub['yhat_upper'] if has_interval else None)
    return out


def pooled_bucket_metrics(frames):
    """Metrics pooled over the rows of several folds."""
    return bucket_metrics(pd.concat(frames, ignore_index=True)) if frames else {}


def lead_time_calibration(fold, lead_time, alpha):
    """(hit, rop, actual lead-time demand) for one test fold with stored sample paths."""
    rop = float(np.quantile(fold.cumulative_paths[:, lead_time - 1], alpha))
    actual = float(fold.frame.loc[fold.frame['h'] <= lead_time, 'actual'].sum())
    return actual <= rop, rop, actual


# --------------------------------------------------------------------------- orchestration

def evaluate_history(history, holidays_frame, uncertainty_samples=None, horizon=None, initial=None,
                     period=None, n_test=None, min_selection=None, arms=None, progress=None):
    """Run the full evaluation for one product's history. Pure compute, no database.

    Returns a dict with cutoffs, ablation scores/log, selected arm, test-fold metrics for Prophet and
    both baselines, and service-level calibration rows.
    """
    horizon = horizon or Config.MAX_FORECAST_DAYS
    initial = initial or Config.CV_INITIAL_DAYS
    period = period or Config.CV_PERIOD_DAYS
    n_test = n_test or Config.N_TEST_FOLDS
    arm_names = list(arms or model_mod.ARMS)
    say = progress or (lambda msg: None)

    cutoffs = make_cutoffs(history, horizon, initial, period)
    selection, test = split_folds(cutoffs, horizon, n_test, min_selection)
    planned = planned_from_actuals(history)

    # 1. Ablation on selection folds only
    selection_frames = {}
    scores = {}
    for arm in arm_names:
        selection_frames[arm] = {}
        scores[arm] = []
        for cutoff in selection:
            fold = run_fold(model_mod.ARMS[arm], history, cutoff, horizon, holidays_frame, planned,
                            uncertainty_samples)
            selection_frames[arm][cutoff] = fold.frame
            m = bucket_metrics(fold.frame)['all']
            scores[arm].append((m['abs_err'], m['actual_sum']))
        say(f'  ablation arm {arm}: pooled selection WAPE {_pooled(scores[arm]):.4f}')
    selected, decisions = select_arm(scores)

    # 2. Held-out test folds: selected arm with sample paths, plus baselines on identical folds
    test_frames = {'prophet': [], 'naive': [], 'seasonal_naive': []}
    calibration = []
    for cutoff in test:
        fold = run_fold(model_mod.ARMS[selected], history, cutoff, horizon, holidays_frame, planned,
                        uncertainty_samples, with_samples=True)
        test_frames['prophet'].append(fold.frame)
        base = baseline_fold(history, cutoff, horizon)
        # keep rows aligned with Prophet's (same actual rows by construction)
        test_frames['naive'].append(base['naive'])
        test_frames['seasonal_naive'].append(base['seasonal_naive'])
        hit, rop, actual = lead_time_calibration(fold, Config.DEFAULT_LEAD_TIME, Config.DEFAULT_SERVICE_LEVEL)
        calibration.append({'fold_cutoff': cutoff, 'lead_time': Config.DEFAULT_LEAD_TIME,
                            'alpha': Config.DEFAULT_SERVICE_LEVEL, 'hit': bool(hit), 'rop': rop,
                            'actual': actual})
    say(f'  selected configuration: {selected}')

    return {
        'cutoffs': {'selection': selection, 'test': test},
        'scores': scores,
        'selection_frames': selection_frames,
        'decisions': decisions,
        'selected_arm': selected,
        'selected_config': dict(model_mod.ARMS[selected]),
        'test_frames': test_frames,
        'test_cutoffs': test,
        'calibration': calibration,
        'cv_params': {'initial_days': initial, 'horizon_days': horizon, 'period_days': period,
                      'n_test_folds': n_test, 'n_selection_folds': len(selection),
                      'uncertainty_samples': uncertainty_samples or Config.UNCERTAINTY_SAMPLES,
                      'ablation_min_rel_gain': Config.ABLATION_MIN_REL_GAIN,
                      'ablation_min_fold_win_share': Config.ABLATION_MIN_FOLD_WIN_SHARE,
                      'verdict_skill_threshold': Config.VERDICT_SKILL_THRESHOLD,
                      'verdict_min_fold_share': Config.VERDICT_MIN_FOLD_SHARE},
    }
