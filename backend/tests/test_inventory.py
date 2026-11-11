from datetime import date

import numpy as np
import pytest

import inventory as inv

pytestmark = pytest.mark.unit

AS_OF = date(2024, 12, 31)


def make_paths(n=2000, horizon=90, mean=100.0, sd=15.0, seed=1):
    rng = np.random.default_rng(seed)
    daily = np.clip(rng.normal(mean, sd, (n, horizon)), 0, None)
    return daily.cumsum(axis=1)


PATHS = make_paths()


def test_default_recommendation_matches_quantile_definition():
    r = inv.recommend(PATHS, AS_OF)
    demand = PATHS[:, 6]
    assert r['lead_time'] == 7 and r['service_level'] == 0.95
    assert r['reorder_point'] == pytest.approx(np.quantile(demand, 0.95))
    assert r['safety_stock'] == pytest.approx(np.quantile(demand, 0.95) - demand.mean())
    assert r['mean_lead_time_demand'] == pytest.approx(demand.mean())
    assert 'on_hand' not in r and r['assumptions']


def test_monotone_in_service_level():
    ss = [inv.recommend(PATHS, AS_OF, 7, a)['safety_stock'] for a in (0.6, 0.8, 0.9, 0.95, 0.99)]
    rop = [inv.recommend(PATHS, AS_OF, 7, a)['reorder_point'] for a in (0.6, 0.8, 0.9, 0.95, 0.99)]
    assert ss == sorted(ss) and rop == sorted(rop)


def test_stock_out_probability_monotone_in_on_hand():
    ps = [inv.stock_out_probability(PATHS, 7, oh) for oh in (0, 400, 600, 700, 800, 2000)]
    assert ps == sorted(ps, reverse=True)
    assert ps[0] == 1.0 and ps[-1] == 0.0


def test_on_hand_equal_to_reorder_point_is_ok_and_reorder_now():
    rop = inv.reorder_point(PATHS, 7, 0.95)
    r = inv.recommend(PATHS, AS_OF, 7, 0.95, on_hand=rop)
    assert r['risk_level'] == 'ok' and r['reorder_now'] is True
    assert r['stock_out_probability'] <= 0.05 + 1e-9


def test_above_reorder_point_does_not_reorder():
    rop = inv.reorder_point(PATHS, 7, 0.95)
    assert inv.recommend(PATHS, AS_OF, 7, 0.95, on_hand=rop + 100)['reorder_now'] is False


def test_zero_on_hand_is_high_risk_and_stocks_out_on_day_one():
    r = inv.recommend(PATHS, AS_OF, 7, 0.95, on_hand=0)
    assert r['risk_level'] == 'high' and r['stock_out_probability'] == 1.0
    assert r['projected_stock_out_date'] == '2025-01-01'       # first forecast day
    assert r['earliest_likely_stock_out_date'] == '2025-01-01'
    assert r['beyond_horizon'] is False


def test_elevated_band():
    # on-hand at the 70th percentile of lead-time demand -> P ~ 0.30: above 1-alpha, below 0.5
    oh = float(np.quantile(PATHS[:, 6], 0.70))
    assert inv.recommend(PATHS, AS_OF, 7, 0.95, on_hand=oh)['risk_level'] == 'elevated'
    assert inv.risk_level(0.5, 0.95) == 'high' and inv.risk_level(0.05, 0.95) == 'ok'


def test_beyond_horizon():
    r = inv.recommend(PATHS, AS_OF, 7, 0.95, on_hand=1e9)
    assert r['projected_stock_out_date'] is None and r['earliest_likely_stock_out_date'] is None
    assert r['beyond_horizon'] is True and r['risk_level'] == 'ok'


def test_earliest_likely_date_not_after_projected():
    r = inv.recommend(PATHS, AS_OF, 7, 0.95, on_hand=1500)
    assert r['earliest_likely_stock_out_date'] <= r['projected_stock_out_date']


def test_lead_time_scaling():
    r7, r14 = inv.recommend(PATHS, AS_OF, 7), inv.recommend(PATHS, AS_OF, 14)
    assert r14['mean_lead_time_demand'] == pytest.approx(2 * r7['mean_lead_time_demand'], rel=0.02)
    assert r14['reorder_point'] > r7['reorder_point']
    # uncertainty grows ~sqrt(L): safety stock grows by less than the mean does
    assert r14['safety_stock'] / r7['safety_stock'] < 2


@pytest.mark.parametrize('lead, alpha, on_hand', [
    (0, 0.95, 0), (-3, 0.95, 0), (91, 0.95, 0), (7.5, 0.95, 0), ('7', 0.95, 0),
    (7, 0.5, 0), (7, 0.999, 0), (7, 1.2, 0), (7, 0.95, -1),
])
def test_validation(lead, alpha, on_hand):
    with pytest.raises(inv.ParameterError):
        inv.recommend(PATHS, AS_OF, lead, alpha, on_hand)
