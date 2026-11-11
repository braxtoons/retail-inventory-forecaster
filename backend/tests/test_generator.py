from datetime import date

import pytest

from generate_sample_data import generate

pytestmark = pytest.mark.unit


def test_same_seed_identical_tables():
    a, b = generate(seed=3), generate(seed=3)
    assert a.keys() == b.keys()
    for key in a:
        assert a[key].equals(b[key]), key


def test_different_seed_differs():
    assert not generate(seed=3)['sales'].equals(generate(seed=4)['sales'])


def test_shape_and_ground_truth_features():
    t = generate()
    sales = t['sales']
    assert sales['sale_date'].max() == date(2024, 12, 31)
    assert not ((sales['sale_date'].map(lambda d: (d.month, d.day)) == (12, 25))).any()   # closures absent
    produce = sales[sales.product_id == 2].quantity_sold
    assert (produce % 1 != 0).any()                                                         # fractional product
    assert set(t['holidays'].type) >= {'Holiday', 'Transfer', 'Additional', 'Bridge', 'Work Day', 'Event'}
    assert (t["planned"].date > date(2024, 12, 31)).all() and (t["planned"].on_promotion > 0).any()
