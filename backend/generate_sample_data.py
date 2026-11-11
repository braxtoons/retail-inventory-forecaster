"""Seeded synthetic dataset shaped like Favorita (ADR-0011).

Writes the same tables as import_kaggle_store_sales.py, so everything downstream (forecasting,
evaluation, API) cannot tell the difference. Ground truth is known by construction, which is what
the slow tests assert against:

  * promotions have a positive, additive effect (`gamma` units of demand per promoted item);
  * oil price is a random walk with NO effect on demand;
  * holidays use every ADR-0004 type: recurring holidays, one transferred holiday with its
    `Transfer` row, `Additional` offset days, `Event`s (Mother's Day, Black Friday), a `Bridge` and
    a `Work Day`, a one-off shock event (earthquake) and a regional/local row that is ignored;
  * Dec 25 has no sales rows (closure, treated as missing);
  * one product (PRODUCE) is weighed and has fractional quantities.

Parameters (module constants / CLI flags):
  SEED        random seed (default 7); same seed => identical tables
  AS_OF       last history date (default 2024-12-31)
  YEARS       length of history in years (default 3, i.e. ~1096 days)
  PLANNED_DAYS  planned-promotion window after AS_OF (default 30 days)
"""
import argparse
from datetime import date, timedelta

import numpy as np
import pandas as pd
from psycopg2.extras import execute_values

from database import get_connection

SEED = 7
AS_OF = date(2024, 12, 31)
YEARS = 3
PLANNED_DAYS = 30

# name, category, unit_price, base level, trend/yr, yearly amplitude, promo gamma (units/promoted item),
# noise sd (fraction), weighed
PRODUCTS = [
    ('BEVERAGES', 'Grocery', 3.99, 1200.0, 0.06, 0.12, 5.0, 0.05, False),
    ('PRODUCE', 'Grocery', 4.99, 800.0, 0.03, 0.18, 3.0, 0.06, True),
    ('DAIRY', 'Grocery', 5.99, 500.0, 0.04, 0.08, 2.5, 0.05, False),
    ('CLEANING', 'Home', 8.99, 300.0, 0.02, 0.05, 2.0, 0.07, False),
]
WEEKLY = np.array([0.90, 0.90, 0.95, 1.00, 1.10, 1.25, 1.15])  # Mon..Sun


def _nth_weekday(year, month, weekday, n):
    d = date(year, month, 1)
    d += timedelta(days=(weekday - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def build_holidays(as_of=AS_OF, years=YEARS):
    """Return (holiday rows DataFrame in the Kaggle schema, {date: demand multiplier})."""
    rows, mult = [], {}
    first_year = as_of.year - years
    last_year = as_of.year + 1

    def add(d, kind, locale, name, desc, transferred=False, m=None):
        rows.append((d, kind, locale, name, desc, transferred))
        if m is not None:
            mult[d] = mult.get(d, 1.0) * m

    for y in range(first_year, last_year + 1):
        add(date(y, 1, 1), 'Holiday', 'National', 'Ecuador', 'Primer dia del ano', m=0.75)
        add(date(y, 5, 1), 'Holiday', 'National', 'Ecuador', 'Dia del Trabajo', m=1.35)
        add(date(y, 12, 24), 'Additional', 'National', 'Ecuador', 'Navidad-1', m=1.5)
        add(date(y, 12, 25), 'Holiday', 'National', 'Ecuador', 'Navidad')  # closed: no sales rows
        add(date(y, 12, 26), 'Additional', 'National', 'Ecuador', 'Navidad+1', m=1.2)
        add(_nth_weekday(y, 5, 6, 2), 'Event', 'National', 'Ecuador', 'Dia de la Madre', m=1.4)
        add(_nth_weekday(y, 11, 4, 4), 'Event', 'National', 'Ecuador', 'Black Friday', m=1.45)
        add(date(y, 12, 6), 'Holiday', 'Local', 'Quito', 'Fundacion de Quito')  # ignored
        if y == 2023:
            # Independence Day transferred from Thursday Aug 10 to Friday Aug 11
            add(date(y, 8, 10), 'Holiday', 'National', 'Ecuador', 'Independencia', transferred=True)
            add(date(y, 8, 11), 'Transfer', 'National', 'Ecuador', 'Traslado Independencia', m=1.3)
        else:
            add(date(y, 8, 10), 'Holiday', 'National', 'Ecuador', 'Independencia', m=1.3)

    # Bridge day and its make-up work day
    add(date(2023, 12, 26), 'Bridge', 'National', 'Ecuador', 'Puente Navidad', m=0.8)
    add(date(2024, 1, 6), 'Work Day', 'National', 'Ecuador', 'Recupero puente Navidad', m=1.15)

    # One-off shock event: demand collapses, then recovers over 11 days
    quake = date(2023, 4, 16)
    for k in range(11):
        add(quake + timedelta(days=k), 'Event', 'National', 'Ecuador',
            'Terremoto Test' if k == 0 else f'Terremoto Test+{k}', m=0.6 + 0.04 * k)

    df = pd.DataFrame(rows, columns=['date', 'type', 'locale', 'locale_name', 'description', 'transferred'])
    return df.sort_values(['date', 'description']).reset_index(drop=True), mult


def _promo_series(rng, dates, p_start=0.04):
    """Promotion episodes of 3-14 days at an intensity of 10-100 promoted items."""
    n = len(dates)
    promo = np.zeros(n)
    i = 0
    while i < n:
        if rng.random() < p_start:
            length = int(rng.integers(3, 15))
            promo[i:i + length] = float(rng.integers(10, 101))
            i += length
        else:
            i += 1
    return promo


def generate(seed=SEED, as_of=AS_OF, years=YEARS, planned_days=PLANNED_DAYS):
    """Build every table as a DataFrame. Pure and deterministic in its arguments."""
    rng = np.random.default_rng(seed)
    start = as_of - timedelta(days=int(round(365.25 * years)) - 1)
    dates = pd.date_range(start, as_of, freq='D')
    holidays_df, mult = build_holidays(as_of, years)

    # Oil: random walk on business days, no effect on demand
    biz = dates[dates.dayofweek < 5]
    oil = np.maximum(20.0, 60.0 + np.cumsum(rng.normal(0, 0.8, len(biz))))
    oil_df = pd.DataFrame({'date': biz.date, 'dcoilwtico': np.round(oil, 2)})

    hol_mult = np.array([mult.get(d.date(), 1.0) for d in dates])
    doy = dates.dayofyear.values
    t_years = (np.arange(len(dates))) / 365.25
    closed = (dates.month == 12) & (dates.day == 25)

    sales, planned = [], []
    products = []
    future_dates = pd.date_range(as_of + timedelta(days=1), periods=planned_days, freq='D')
    for idx, (name, category, price, base, trend, amp, gamma, noise, weighed) in enumerate(PRODUCTS, start=1):
        products.append((idx, name, category, price))
        promo = _promo_series(rng, dates)
        level = base * (1 + trend * t_years)
        yearly = 1 + amp * np.sin(2 * np.pi * (doy - 80) / 365.25)
        weekly = WEEKLY[dates.dayofweek.values]
        mean = level * yearly * weekly * hol_mult + gamma * promo
        y = np.maximum(0.0, mean * (1 + rng.normal(0, noise, len(dates))))
        y = np.round(y, 3) if weighed else np.round(y)
        for k in np.flatnonzero(~closed):
            sales.append((idx, dates[k].date(), float(y[k]), round(float(y[k]) * price, 2), int(promo[k])))
        fut = _promo_series(rng, future_dates, p_start=0.05)
        fut[4:11] = np.maximum(fut[4:11], float(rng.integers(30, 80)))   # always at least one planned episode
        # One row per day of the window (0 = nothing planned), so promo_known_through is the window end
        planned += [(idx, d.date(), int(v)) for d, v in zip(future_dates, fut)]

    return {
        'products': pd.DataFrame(products, columns=['product_id', 'product_name', 'category', 'unit_price']),
        'sales': pd.DataFrame(sales, columns=['product_id', 'sale_date', 'quantity_sold', 'total_amount',
                                              'on_promotion']),
        'oil': oil_df,
        'holidays': holidays_df,
        'planned': pd.DataFrame(planned, columns=['product_id', 'date', 'on_promotion']),
    }


def write_to_db(tables):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute('TRUNCATE forecast_run_samples, forecasts, forecast_runs, evaluation_service_level, '
                    'evaluation_metrics, evaluation_runs, planned_promotions, sales_data, oil_prices, '
                    'holidays, products RESTART IDENTITY CASCADE')
        execute_values(cur, 'INSERT INTO products (product_id, product_name, category, unit_price) VALUES %s',
                       [tuple(r) for r in tables['products'].itertuples(index=False)])
        cur.execute("SELECT setval(pg_get_serial_sequence('products', 'product_id'), (SELECT MAX(product_id) FROM products))")
        sales = [(int(r.product_id), r.sale_date, r.quantity_sold, r.total_amount, r.on_promotion)
                 for r in tables['sales'].itertuples(index=False)]
        execute_values(cur, 'INSERT INTO sales_data (product_id, sale_date, quantity_sold, total_amount, on_promotion) '
                            'VALUES %s', sales, page_size=5000)
        execute_values(cur, 'INSERT INTO oil_prices (date, dcoilwtico) VALUES %s',
                       [(r.date, float(r.dcoilwtico)) for r in tables['oil'].itertuples(index=False)])
        execute_values(cur, 'INSERT INTO holidays (date, type, locale, locale_name, description, transferred) '
                            'VALUES %s',
                       [(r.date, r.type, r.locale, r.locale_name, r.description, bool(r.transferred))
                        for r in tables['holidays'].itertuples(index=False)])
        execute_values(cur, 'INSERT INTO planned_promotions (product_id, date, on_promotion) VALUES %s',
                       [(int(r.product_id), r.date, int(r.on_promotion))
                        for r in tables['planned'].itertuples(index=False)])


def generate_sample_data(seed=SEED, as_of=AS_OF, years=YEARS, planned_days=PLANNED_DAYS):
    tables = generate(seed, as_of, years, planned_days)
    write_to_db(tables)
    s = tables['sales']
    print(f"Generated {len(s):,} sales rows for {len(tables['products'])} products "
          f"({s['sale_date'].min()} to {s['sale_date'].max()}), seed={seed}")
    print(f"Planned promotions: {len(tables['planned'])} rows after {as_of}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate the seeded Favorita-shaped synthetic dataset')
    parser.add_argument('--seed', type=int, default=SEED)
    parser.add_argument('--as-of', type=date.fromisoformat, default=AS_OF)
    parser.add_argument('--years', type=int, default=YEARS)
    args = parser.parse_args()
    generate_sample_data(args.seed, args.as_of, args.years)
