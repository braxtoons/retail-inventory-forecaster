"""History queries and data helpers (forecast-data capability).

No query here joins sales to the holiday table: holidays reach Prophet only through its
`holidays=` parameter (ADR-0004), so a date with two holiday rows can never duplicate sales.
"""
import hashlib

import pandas as pd

from config import Config
from database import get_cursor


def get_history(product_id, training_start=None, as_of=None, cur=None):
    """Daily demand for one product, summed across stores.

    Returns a frame with ds, y, on_promotion, oil_price. Closure days have no sales rows, so they
    are absent rather than zero (ADR-0003). `training_start` defaults to the configured window;
    pass `None` explicitly via Config to use all history.
    """
    if training_start is None:
        training_start = Config.TRAINING_START_DATE
    sql = """
        SELECT s.sale_date AS ds,
               SUM(s.quantity_sold)::float8 AS y,
               SUM(s.on_promotion)::float8 AS on_promotion,
               MAX(o.dcoilwtico)::float8 AS oil_price
        FROM sales_data s
        LEFT JOIN oil_prices o ON o.date = s.sale_date
        WHERE s.product_id = %s
          AND (%s::date IS NULL OR s.sale_date >= %s::date)
          AND (%s::date IS NULL OR s.sale_date <= %s::date)
        GROUP BY s.sale_date
        ORDER BY s.sale_date
    """
    params = (product_id, training_start, training_start, as_of, as_of)
    if cur is None:
        with get_cursor() as c:
            c.execute(sql, params)
            rows = c.fetchall()
    else:
        cur.execute(sql, params)
        rows = cur.fetchall()
    return prepare_history(pd.DataFrame(rows, columns=['ds', 'y', 'on_promotion', 'oil_price']))


def prepare_history(df):
    """Type and fill a raw history frame. Oil is forward-filled only (causal); leading gaps take the
    first observed price. Missing promotions mean none."""
    df = df.copy()
    df['ds'] = pd.to_datetime(df['ds'])
    for col in ('y', 'on_promotion', 'oil_price'):
        df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)
    df['on_promotion'] = df['on_promotion'].fillna(0.0)
    if df['oil_price'].notna().any():
        df['oil_price'] = df['oil_price'].ffill().bfill()
    else:
        df['oil_price'] = 0.0
    return df.sort_values('ds').reset_index(drop=True)


def data_fingerprint(n_dates, max_date):
    """Short hash of a product's history: number of dated rows plus the last date."""
    raw = f'{int(n_dates)}:{max_date}'
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def history_fingerprint(df):
    """Fingerprint of an already-loaded history frame (same value as get_fingerprint)."""
    if df.empty:
        return data_fingerprint(0, None)
    return data_fingerprint(len(df), df['ds'].max().date())


def get_fingerprint(product_id, training_start=None, cur=None):
    """Fingerprint straight from the database, within the training window."""
    if training_start is None:
        training_start = Config.TRAINING_START_DATE
    sql = """
        SELECT COUNT(DISTINCT sale_date) AS n, MAX(sale_date) AS max_date
        FROM sales_data
        WHERE product_id = %s AND (%s::date IS NULL OR sale_date >= %s::date)
    """
    params = (product_id, training_start, training_start)
    if cur is None:
        with get_cursor() as c:
            c.execute(sql, params)
            row = c.fetchone()
    else:
        cur.execute(sql, params)
        row = cur.fetchone()
    return data_fingerprint(row['n'], row['max_date'])


def get_planned_promotions(product_id, cur=None):
    """Planned promotions as a Series indexed by Timestamp (empty when none)."""
    sql = "SELECT date, on_promotion::float8 AS on_promotion FROM planned_promotions WHERE product_id = %s ORDER BY date"
    if cur is None:
        with get_cursor() as c:
            c.execute(sql, (product_id,))
            rows = c.fetchall()
    else:
        cur.execute(sql, (product_id,))
        rows = cur.fetchall()
    if not rows:
        return pd.Series(dtype=float, name='on_promotion')
    s = pd.Series([r['on_promotion'] for r in rows], index=pd.to_datetime([r['date'] for r in rows]),
                  name='on_promotion')
    return s


def promo_known_through(planned):
    """Last date with planned-promotion data, or None."""
    return None if planned is None or planned.empty else planned.index.max().date()


def get_holidays_table(cur=None):
    """Raw holidays rows (all locales); filtering to national happens in holiday_frame."""
    sql = "SELECT date, type, locale, locale_name, description, transferred FROM holidays ORDER BY date"
    if cur is None:
        with get_cursor() as c:
            c.execute(sql)
            rows = c.fetchall()
    else:
        cur.execute(sql)
        rows = cur.fetchall()
    return pd.DataFrame(rows, columns=['date', 'type', 'locale', 'locale_name', 'description', 'transferred'])
