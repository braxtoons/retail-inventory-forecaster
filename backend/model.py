"""The single model factory and future-frame builder shared by production and CV (ADR-0002).

Everything that scores or ships a forecast goes through `build_model` and `build_future_frame`,
which is what guarantees rolling CV measures the same thing production does.
"""
import logging

import numpy as np
import pandas as pd

from config import Config

logging.getLogger('cmdstanpy').setLevel(logging.WARNING)
logging.getLogger('prophet').setLevel(logging.WARNING)

# Ablation arms (ADR-0007). `holidays` toggles the holidays frame, the others add a regressor.
ARMS = {
    'none': {'holidays': False, 'promo': False, 'oil': False},
    'holidays': {'holidays': True, 'promo': False, 'oil': False},
    'holidays+promo': {'holidays': True, 'promo': True, 'oil': False},
    'holidays+oil': {'holidays': True, 'promo': False, 'oil': True},
    'holidays+promo+oil': {'holidays': True, 'promo': True, 'oil': True},
}
DEFAULT_CONFIG = dict(ARMS['holidays'])
REGRESSOR_COLUMNS = {'promo': 'on_promotion', 'oil': 'oil_price'}


def normalize_config(config):
    """Canonical `{holidays, promo, oil}` booleans (missing keys are False)."""
    config = config or {}
    return {k: bool(config.get(k, False)) for k in ('holidays', 'promo', 'oil')}


def arm_name(config):
    config = normalize_config(config)
    for name, arm in ARMS.items():
        if arm == config:
            return name
    return 'custom'


def build_model(config, holidays_frame=None, uncertainty_samples=None):
    """A Prophet model for `config`. Holidays go in only via `holidays=`; regressors per config."""
    from prophet import Prophet  # imported lazily: keeps the unit tier free of Stan/pandas start-up cost

    config = normalize_config(config)
    use_holidays = config['holidays'] and holidays_frame is not None and len(holidays_frame) > 0
    model = Prophet(
        yearly_seasonality=True,
        weekly_seasonality=True,
        daily_seasonality=False,
        interval_width=0.95,
        holidays=holidays_frame if use_holidays else None,
        uncertainty_samples=uncertainty_samples or Config.UNCERTAINTY_SAMPLES,
    )
    for key, column in REGRESSOR_COLUMNS.items():
        if config[key]:
            model.add_regressor(column)
    return model


def training_frame(history, config):
    """The columns a model built from `config` is fitted on."""
    config = normalize_config(config)
    cols = ['ds', 'y'] + [c for k, c in REGRESSOR_COLUMNS.items() if config[k]]
    return history[cols]


def build_future_frame(history, horizon, as_of, planned_promotions=None):
    """Future regressor values for the `horizon` days after `as_of` (regressor knowledge policy).

    * holidays: supplied through Prophet's `holidays=` parameter, so nothing to add here;
    * promotions: planned promotions, 0 where none are planned;
    * oil price: the last observed value on or before `as_of`, carried forward.

    `history` only needs to cover dates up to `as_of`; later rows are ignored.
    """
    as_of = pd.Timestamp(as_of)
    ds = pd.date_range(as_of + pd.Timedelta(days=1), periods=int(horizon), freq='D')
    future = pd.DataFrame({'ds': ds})

    if planned_promotions is None or len(planned_promotions) == 0:
        future['on_promotion'] = 0.0
    else:
        future['on_promotion'] = planned_promotions.reindex(ds).fillna(0.0).astype(float).to_numpy()

    seen = history[history['ds'] <= as_of]
    oil = seen['oil_price'].dropna()
    future['oil_price'] = float(oil.iloc[-1]) if len(oil) else 0.0
    return future


def fit_predict(config, history, future, holidays_frame=None, uncertainty_samples=None, seed=None):
    """Fit on `history` and predict `future`. Returns (forecast frame, model)."""
    model = build_model(config, holidays_frame, uncertainty_samples)
    model.fit(training_frame(history, config))
    if seed is not None:
        np.random.seed(seed)
    forecast = model.predict(future)
    return forecast, model


def cumulative_sample_paths(model, future, seed):
    """Seeded predictive sample paths as cumulative demand, shape (n_samples, horizon).

    Daily demand is clipped at 0 before accumulating (ADR-0008)."""
    np.random.seed(seed)
    daily = np.asarray(model.predictive_samples(future)['yhat'], dtype=float)  # (horizon, n_samples)
    return np.clip(daily, 0.0, None).cumsum(axis=0).T
