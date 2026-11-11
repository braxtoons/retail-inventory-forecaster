import numpy as np
import pandas as pd
import pytest

import evaluation as ev
import forecast_runs

pytestmark = pytest.mark.unit


# ---- metrics ------------------------------------------------------------------------------------

def test_metrics_hand_computed():
    actual = [10, 20, 30, 40]
    pred = [12, 18, 33, 36]
    m = ev.compute_metrics(actual, pred, lower=[9, 19, 25, 35], upper=[15, 22, 32, 45])
    # errors 2,2,3,4 -> MAE 2.75; squared 4,4,9,16 -> RMSE sqrt(8.25); WAPE 11/100
    assert m['mae'] == pytest.approx(2.75)
    assert m['rmse'] == pytest.approx(np.sqrt(8.25))
    assert m['wape'] == pytest.approx(0.11)
    # MAPE = mean(.2, .1, .1, .1) = 12.5%
    assert m['mape'] == pytest.approx(12.5)
    assert m['mape_excluded'] == 0
    # 10 in [9,15] yes, 20 in [19,22] yes, 30 in [25,32] yes, 40 in [35,45] yes
    assert m['coverage'] == 1.0 and m['n'] == 4


def test_metrics_zero_actuals_excluded_from_mape_but_not_wape():
    m = ev.compute_metrics([0, 10, 0, 20], [1, 12, 2, 18])
    assert m['mape_excluded'] == 2
    assert m['mape'] == pytest.approx(((2 / 10) + (2 / 20)) / 2 * 100)
    assert m['wape'] == pytest.approx((1 + 2 + 2 + 2) / 30)      # computed over all rows


def test_metrics_all_zero_actuals():
    m = ev.compute_metrics([0, 0], [1, 1])
    assert m['wape'] is None and m['mape'] is None and m['mape_excluded'] == 2


def test_coverage_partial():
    m = ev.compute_metrics([10, 50], [10, 10], lower=[5, 5], upper=[15, 15])
    assert m['coverage'] == 0.5


def test_skill():
    assert ev.skill(0.8, 1.0) == pytest.approx(0.2)
    assert ev.skill(1.2, 1.0) == pytest.approx(-0.2)
    assert ev.skill(None, 1.0) is None and ev.skill(0.5, 0) is None


# ---- folds --------------------------------------------------------------------------------------

def daily(n, start='2020-01-01', skip=()):
    ds = pd.date_range(start, periods=n)
    ds = ds[~ds.isin(pd.to_datetime(list(skip)))]
    return pd.DataFrame({'ds': ds, 'y': np.arange(len(ds), dtype=float) + 100.0})


def test_cutoff_generation_and_split():
    hist = daily(1100)
    cutoffs = ev.make_cutoffs(hist, 90, 365, 60)
    assert cutoffs == sorted(cutoffs)
    assert cutoffs[-1] == hist.ds.max() - pd.Timedelta(days=90)
    assert all(b - a == pd.Timedelta(days=60) for a, b in zip(cutoffs, cutoffs[1:]))
    selection, test = ev.split_folds(cutoffs, 90, 3, 3)
    assert test == cutoffs[-3:]
    # selection windows end on/before the first test cutoff; the fold overlapping the test period is dropped
    assert all(c + pd.Timedelta(days=90) <= test[0] for c in selection)
    assert cutoffs[-4] not in selection
    assert selection == cutoffs[:len(selection)] and len(selection) >= 3


def test_split_raises_with_required_history():
    hist = daily(600)
    with pytest.raises(ev.InsufficientHistory) as exc:
        selection, test = ev.split_folds(ev.make_cutoffs(hist, 90, 365, 60), 90, 3, 3)
    assert exc.value.required_days == ev.min_history_days() == 815


def test_min_history_matches_actual_fold_generation():
    need = ev.min_history_days()
    ok = daily(need + 1)
    ev.split_folds(ev.make_cutoffs(ok, 90, 365, 60), 90, 3, 3)       # enough
    with pytest.raises(ev.InsufficientHistory):
        ev.split_folds(ev.make_cutoffs(daily(need - 70), 90, 365, 60), 90, 3, 3)


# ---- baselines ----------------------------------------------------------------------------------

def test_naive_and_seasonal_naive():
    hist = daily(30)
    cutoff = hist.ds.iloc[-1]
    assert (ev.naive_forecast(hist, cutoff, 10) == hist.y.iloc[-1]).all()
    sn = ev.seasonal_naive_forecast(hist, cutoff, 14)
    last_week = hist.y.iloc[-7:].to_numpy()
    assert np.allclose(sn[:7], last_week) and np.allclose(sn[7:], last_week)   # repeats the last observed week


def test_seasonal_naive_missing_lag_falls_back_to_prior_observation():
    hist = daily(30)
    missing = hist.ds.iloc[-3]                       # a closure day inside the last week
    hist = hist[hist.ds != missing]
    cutoff = hist.ds.iloc[-1]
    sn = ev.seasonal_naive_forecast(hist, cutoff, 7)
    k = (missing - cutoff).days + 7 - 1              # forecast index whose lag date is the missing day
    prior = hist.loc[hist.ds < missing, 'y'].iloc[-1]
    assert sn[k] == prior


# ---- verdicts -----------------------------------------------------------------------------------

@pytest.mark.parametrize('skill_v, wins, losses, n, expected', [
    (0.02, 3, 0, 3, 'comparable'),        # small difference
    (0.10, 2, 1, 3, 'beats'),
    (0.10, 1, 2, 3, 'comparable'),        # skill is fine but no fold majority
    (-0.10, 0, 3, 3, 'worse'),
    (-0.10, 1, 2, 3, 'worse'),
    (-0.10, 2, 1, 3, 'comparable'),
    (0.05, 3, 0, 3, 'beats'),             # threshold is inclusive
    (-0.05, 0, 3, 3, 'worse'),
    (None, 0, 0, 3, 'comparable'),
])
def test_verdict(skill_v, wins, losses, n, expected):
    assert ev.verdict(skill_v, wins, losses, n, 0.05, 2 / 3) == expected


# ---- ablation rule on made-up scores ------------------------------------------------------------

def scores(**arms):
    return {k: v for k, v in arms.items()}


def folds(wape_list, actual=100.0):
    return [(w * actual, actual) for w in wape_list]


def test_ablation_keeps_default_when_nothing_helps():
    s = {'none': folds([.30] * 4), 'holidays': folds([.20] * 4),
         'holidays+promo': folds([.199] * 4),      # 0.5% better: below the 2% margin
         'holidays+oil': folds([.21] * 4), 'holidays+promo+oil': folds([.2] * 4)}
    arm, _ = ev.select_arm(s, 0.02, 2 / 3)
    assert arm == 'holidays'


def test_ablation_accepts_promo_and_rejects_oil():
    s = {'none': folds([.30] * 4), 'holidays': folds([.20] * 4),
         'holidays+promo': folds([.15] * 4),
         'holidays+oil': folds([.199] * 4),
         'holidays+promo+oil': folds([.1495] * 4)}  # oil adds 0.3% on top of promo: rejected
    arm, log = ev.select_arm(s, 0.02, 2 / 3)
    assert arm == 'holidays+promo'
    assert any(d['candidate'] == 'holidays+promo+oil' and not d['accepted'] for d in log)


def test_ablation_requires_fold_wins_not_just_average_gain():
    # promo wins big in one fold and loses in the other three: pooled gain exists, fold-win share does not
    s = {'none': folds([.3] * 4), 'holidays': folds([.20, .20, .20, .20]),
         'holidays+promo': folds([.02, .21, .21, .21]),
         'holidays+oil': folds([.2] * 4), 'holidays+promo+oil': folds([.2] * 4)}
    arm, _ = ev.select_arm(s, 0.02, 2 / 3)
    assert arm == 'holidays'


def test_ablation_can_add_both_greedily_and_drop_holidays():
    s = {'none': folds([.10] * 4), 'holidays': folds([.20] * 4),     # holidays hurt: dropping them wins
         'holidays+promo': folds([.2] * 4), 'holidays+oil': folds([.2] * 4),
         'holidays+promo+oil': folds([.2] * 4)}
    assert ev.select_arm(s, 0.02, 2 / 3)[0] == 'none'
    s = {'none': folds([.3] * 4), 'holidays': folds([.20] * 4), 'holidays+promo': folds([.15] * 4),
         'holidays+oil': folds([.18] * 4), 'holidays+promo+oil': folds([.10] * 4)}
    assert ev.select_arm(s, 0.02, 2 / 3)[0] == 'holidays+promo+oil'


# ---- staleness (pure) ---------------------------------------------------------------------------

def test_staleness_rules():
    cfg = {'holidays': True, 'promo': False, 'oil': False}
    assert forecast_runs.staleness(cfg, 'a', cfg, 'a') == (False, None)
    assert forecast_runs.staleness(cfg, 'a', {**cfg, 'promo': True}, 'a')[0] is True
    stale, reason = forecast_runs.staleness(cfg, 'a', cfg, 'b')
    assert stale and 'data' in reason
