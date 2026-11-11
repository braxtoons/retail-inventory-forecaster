"""Prophet `holidays` frame built from Kaggle holiday rows (ADR-0004).

Named holiday_frame.py, not holidays.py: a top-level `holidays` module would shadow the PyPI
`holidays` package that Prophet imports.
"""
import re

import pandas as pd

WORLD_CUP = 'world_cup_2014'
EARTHQUAKE = 'earthquake_2016'

_SUFFIX = re.compile(r'\s*[+-]\d+$')
_TRASLADO = re.compile(r'^\s*Traslado\s+', re.IGNORECASE)


def _truthy(value):
    if isinstance(value, str):
        return value.strip().lower() in ('true', 't', '1')
    return bool(value)


def build_holidays_frame(raw):
    """Return a frame with columns ds, holiday, lower_window, upper_window.

    `raw` has the columns of the `holidays` table (date, type, locale, description, transferred).
    Only national rows are used; regional and local holidays are ignored.
    """
    cols = ['ds', 'holiday', 'lower_window', 'upper_window']
    if raw is None or len(raw) == 0:
        return pd.DataFrame(columns=cols)

    df = raw[raw['locale'] == 'National'].copy()
    df['date'] = pd.to_datetime(df['date'])
    df['description'] = df['description'].fillna('').astype(str).str.strip()
    rows = []
    shocks = {WORLD_CUP: [], EARTHQUAKE: []}

    for r in df.itertuples():
        kind, desc = r.type, r.description
        if kind == 'Holiday':
            if _truthy(r.transferred):
                continue  # a normal trading day that year
            rows.append((r.date, desc))
        elif kind == 'Transfer':
            rows.append((r.date, _TRASLADO.sub('', desc)))
        elif kind == 'Additional':
            rows.append((r.date, desc))
        elif kind == 'Bridge':
            rows.append((r.date, 'bridge'))
        elif kind == 'Work Day':
            rows.append((r.date, 'work_day'))
        elif kind == 'Event':
            low = desc.lower()
            if 'mundial' in low:
                shocks[WORLD_CUP].append(r.date)
            elif 'terremoto' in low:
                shocks[EARTHQUAKE].append(r.date)
            else:
                rows.append((r.date, _SUFFIX.sub('', desc)))

    out = [{'ds': d, 'holiday': name, 'lower_window': 0, 'upper_window': 0} for d, name in rows]
    for name, dates in shocks.items():
        if dates:
            first, last = min(dates), max(dates)
            # One non-recurring holiday spanning the whole episode (ADR-0003).
            out.append({'ds': first, 'holiday': name, 'lower_window': 0,
                        'upper_window': int((last - first).days)})

    frame = pd.DataFrame(out, columns=cols)
    frame = frame.drop_duplicates(subset=['ds', 'holiday']).sort_values(['ds', 'holiday'])
    return frame.reset_index(drop=True)
