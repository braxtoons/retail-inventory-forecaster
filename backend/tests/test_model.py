import numpy as np
import pandas as pd
import pytest

import model as m

pytestmark = pytest.mark.unit


def make_history(n=400, start='2022-01-01'):
    ds = pd.date_range(start, periods=n)
    rng = np.random.default_rng(0)
    return pd.DataFrame({
        'ds': ds, 'y': 100 + rng.normal(0, 5, n),
        'on_promotion': (np.arange(n) % 9 == 0).astype(float) * 20,
        'oil_price': 50 + np.cumsum(rng.normal(0, 1, n)),
    })


HOLS = pd.DataFrame({'ds': pd.to_datetime(['2022-05-01']), 'holiday': ['labour'],
                     'lower_window': 0, 'upper_window': 0})


def test_build_model_registers_regressors_and_holidays():
    model = m.build_model(m.ARMS['holidays+promo+oil'], HOLS, uncertainty_samples=10)
    assert set(model.extra_regressors) == {'on_promotion', 'oil_price'}
    assert model.holidays is not None and list(model.holidays['holiday']) == ['labour']


def test_build_model_default_is_holidays_only():
    model = m.build_model(m.DEFAULT_CONFIG, HOLS, uncertainty_samples=10)
    assert not model.extra_regressors and model.holidays is not None


def test_none_arm_has_no_holidays_or_regressors():
    model = m.build_model(m.ARMS['none'], HOLS, uncertainty_samples=10)
    assert not model.extra_regressors and model.holidays is None


def test_arm_names_round_trip():
    for name, cfg in m.ARMS.items():
        assert m.arm_name(cfg) == name


def test_future_frame_policy():
    hist = make_history()
    as_of = hist.ds.iloc[300]
    planned = pd.Series([7.0, 3.0], index=pd.to_datetime([as_of + pd.Timedelta(days=2), as_of + pd.Timedelta(days=5)]))
    fut = m.build_future_frame(hist, 10, as_of, planned)
    assert list(fut.ds) == list(pd.date_range(as_of + pd.Timedelta(days=1), periods=10))
    assert fut.on_promotion.tolist() == [0, 7, 0, 0, 3, 0, 0, 0, 0, 0]          # planned, else 0
    assert (fut.oil_price == hist.oil_price.iloc[300]).all()                     # last value <= as_of, no leakage


def test_future_frame_parity_between_production_and_cv_cutoff():
    full = make_history()
    cutoff = full.ds.iloc[250]
    planned = full.set_index('ds')['on_promotion']      # CV: actual promotions stand in for planned
    production = m.build_future_frame(full[full.ds <= cutoff], 90, cutoff, planned)   # history ends at the as-of date
    cv = m.build_future_frame(full, 90, cutoff, planned)                              # extra later rows are ignored
    pd.testing.assert_frame_equal(production, cv)


def test_future_frame_without_planned_promotions_is_zero():
    hist = make_history(50)
    fut = m.build_future_frame(hist, 5, hist.ds.max(), None)
    assert (fut.on_promotion == 0).all()
