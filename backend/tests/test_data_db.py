import pandas as pd
import pytest

import data
from generate_sample_data import generate, write_to_db

pytestmark = pytest.mark.db


@pytest.fixture()
def seeded(db):
    tables = generate()
    write_to_db(tables)
    return tables


def test_no_double_counting_on_dates_with_multiple_national_holiday_rows(seeded):
    """Regression: the old holiday LEFT JOIN multiplied sales on dates with two holiday rows."""
    hol = seeded['holidays']
    national = hol[hol.locale == 'National']
    counts = national.groupby('date').size()
    multi = list(counts[counts > 1].index)
    assert multi, 'fixture should contain dates with several national holiday rows'

    raw = seeded['sales'][seeded['sales'].product_id == 1].set_index('sale_date')['quantity_sold']
    hist = data.get_history(1, training_start=None).set_index('ds')['y']
    checked = 0
    for d in multi:
        ts = pd.Timestamp(d)
        if d in raw.index:
            assert hist[ts] == pytest.approx(raw[d])
            checked += 1
    assert checked >= 1
    assert hist.sum() == pytest.approx(raw.sum())


def test_closure_days_absent_not_zero(seeded):
    hist = data.get_history(1, training_start=None)
    assert not ((hist.ds.dt.month == 12) & (hist.ds.dt.day == 25)).any()


def test_fractional_quantities_preserved(seeded):
    hist = data.get_history(2, training_start=None)
    raw = seeded['sales'][seeded['sales'].product_id == 2].set_index('sale_date')['quantity_sold']
    assert (hist.y % 1 != 0).any()
    assert hist.set_index('ds').y.iloc[0] == pytest.approx(raw.iloc[0], abs=1e-3)


def test_training_window_respected(seeded):
    hist = data.get_history(1, training_start=pd.Timestamp('2024-01-01').date())
    assert hist.ds.min() >= pd.Timestamp('2024-01-01')


def test_planned_promotions_and_fingerprint(seeded):
    planned = data.get_planned_promotions(1)
    assert data.promo_known_through(planned) is None or data.promo_known_through(planned) > pd.Timestamp('2024-12-31').date()
    fp = data.get_fingerprint(1, training_start=None)
    assert fp == data.history_fingerprint(data.get_history(1, training_start=None))
