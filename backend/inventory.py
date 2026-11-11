"""Inventory recommendations as pure functions over cumulative demand sample paths (ADR-0008, ADR-0009).

`paths` is an array of shape (n_samples, horizon): cumulative demand (daily values already clipped at 0)
at the single distribution centre, starting the day after the as-of date.
"""
from datetime import timedelta

import numpy as np

from config import Config

ASSUMPTIONS = [
    'Inventory position equals on-hand stock: stock already on order is not counted.',
    'Quantities refer to stock held at the single distribution centre, pooled across all stores.',
    'Service level is the cycle service level: the probability of not running out during one lead time.',
]


class ParameterError(ValueError):
    pass


def validate_params(lead_time, service_level, on_hand=None, horizon=None):
    """Raise ParameterError with a descriptive message for invalid inputs."""
    horizon = horizon or Config.MAX_FORECAST_DAYS
    if isinstance(lead_time, bool) or not isinstance(lead_time, (int, np.integer)):
        raise ParameterError('lead_time must be an integer number of days')
    if not 1 <= lead_time <= min(Config.MAX_LEAD_TIME, horizon):
        raise ParameterError(f'lead_time must be between 1 and {min(Config.MAX_LEAD_TIME, horizon)} days')
    if not isinstance(service_level, (int, float, np.floating)) or not 0.5 < service_level < 0.999:
        raise ParameterError('service_level must be between 0.5 and 0.999 (exclusive)')
    if on_hand is not None and (not isinstance(on_hand, (int, float, np.floating)) or on_hand < 0
                                or not np.isfinite(on_hand)):
        raise ParameterError('on_hand must be a number greater than or equal to 0')


def lead_time_demand(paths, lead_time):
    """Cumulative demand at the end of day `lead_time` for every path."""
    return np.asarray(paths)[:, lead_time - 1]


def reorder_point(paths, lead_time, service_level):
    """alpha-quantile of lead-time demand."""
    return float(np.quantile(lead_time_demand(paths, lead_time), service_level))


def safety_stock(paths, lead_time, service_level):
    """Reorder point minus mean lead-time demand."""
    return reorder_point(paths, lead_time, service_level) - float(lead_time_demand(paths, lead_time).mean())


def stock_out_probability(paths, lead_time, on_hand):
    """Share of paths whose cumulative demand over the lead time exceeds on-hand."""
    return float(np.mean(lead_time_demand(paths, lead_time) > on_hand))


def risk_level(probability, service_level):
    """`ok` if P <= 1 - alpha, `high` if P >= 0.5, else `elevated`."""
    if probability <= (1.0 - service_level) + 1e-12:
        return 'ok'
    if probability >= 0.5:
        return 'high'
    return 'elevated'


def first_exceed_day(path, on_hand):
    """1-based index of the first day cumulative demand exceeds on-hand, or None."""
    over = np.flatnonzero(np.asarray(path) > on_hand)
    return int(over[0]) + 1 if over.size else None


def stock_out_dates(paths, on_hand, as_of):
    """(projected, earliest_likely, beyond_horizon): first day the median / 90th-percentile cumulative path
    exceeds on-hand, searched over the whole stored horizon."""
    paths = np.asarray(paths)
    median_day = first_exceed_day(np.quantile(paths, 0.5, axis=0), on_hand)
    p90_day = first_exceed_day(np.quantile(paths, 0.9, axis=0), on_hand)
    to_date = lambda k: None if k is None else (as_of + timedelta(days=k)).isoformat()
    return to_date(median_day), to_date(p90_day), median_day is None and p90_day is None


def recommend(paths, as_of, lead_time=None, service_level=None, on_hand=None):
    """Full recommendation dict. `on_hand=None` returns only the stocking parameters."""
    lead_time = Config.DEFAULT_LEAD_TIME if lead_time is None else lead_time
    service_level = Config.DEFAULT_SERVICE_LEVEL if service_level is None else service_level
    paths = np.asarray(paths, dtype=float)
    validate_params(lead_time, service_level, on_hand, horizon=paths.shape[1])

    demand = lead_time_demand(paths, lead_time)
    rop = float(np.quantile(demand, service_level))
    out = {
        'lead_time': int(lead_time),
        'service_level': float(service_level),
        'mean_lead_time_demand': float(demand.mean()),
        'reorder_point': rop,
        'safety_stock': rop - float(demand.mean()),
        'assumptions': list(ASSUMPTIONS),
    }
    if on_hand is not None:
        p = stock_out_probability(paths, lead_time, on_hand)
        projected, earliest, beyond = stock_out_dates(paths, on_hand, as_of)
        out.update({
            'on_hand': float(on_hand),
            'stock_out_probability': p,
            'risk_level': risk_level(p, service_level),
            'reorder_now': bool(on_hand <= rop),
            'projected_stock_out_date': projected,
            'earliest_likely_stock_out_date': earliest,
            'beyond_horizon': beyond,
        })
    return out
