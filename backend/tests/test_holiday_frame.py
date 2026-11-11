import pandas as pd
import pytest

from holiday_frame import build_holidays_frame, EARTHQUAKE, WORLD_CUP

pytestmark = pytest.mark.unit


def raw(*rows):
    return pd.DataFrame(rows, columns=['date', 'type', 'locale', 'locale_name', 'description', 'transferred'])


def names_on(frame, day):
    return sorted(frame.loc[frame.ds == pd.Timestamp(day), 'holiday'])


def test_transferred_original_dropped_and_transfer_renamed():
    frame = build_holidays_frame(raw(
        ('2016-05-24', 'Holiday', 'National', 'Ecuador', 'Batalla de Pichincha', True),
        ('2016-05-27', 'Transfer', 'National', 'Ecuador', 'Traslado Batalla de Pichincha', False),
    ))
    assert names_on(frame, '2016-05-24') == []
    assert names_on(frame, '2016-05-27') == ['Batalla de Pichincha']


def test_plain_holiday_additional_and_event_suffix():
    frame = build_holidays_frame(raw(
        ('2015-12-24', 'Additional', 'National', 'Ecuador', 'Navidad-1', False),
        ('2015-01-01', 'Holiday', 'National', 'Ecuador', 'Primer dia del ano', False),
        ('2015-11-27', 'Event', 'National', 'Ecuador', 'Black Friday', False),
        ('2015-11-26', 'Event', 'National', 'Ecuador', 'Black Friday-1', False),
    ))
    assert names_on(frame, '2015-12-24') == ['Navidad-1']  # Additional keeps its own effect per offset
    assert names_on(frame, '2015-01-01') == ['Primer dia del ano']
    assert names_on(frame, '2015-11-26') == ['Black Friday']  # +/-N suffix stripped for recurring events


def test_bridge_and_work_day():
    frame = build_holidays_frame(raw(
        ('2012-12-24', 'Bridge', 'National', 'Ecuador', 'Puente Navidad', False),
        ('2013-01-05', 'Work Day', 'National', 'Ecuador', 'Recupero puente Navidad', False),
    ))
    assert names_on(frame, '2012-12-24') == ['bridge']
    assert names_on(frame, '2013-01-05') == ['work_day']


def test_shock_events_collapse_to_one_non_recurring_holiday():
    rows = [('2016-04-16', 'Event', 'National', 'Ecuador', 'Terremoto Manabi', False)]
    rows += [(f'2016-04-{16 + k}', 'Event', 'National', 'Ecuador', f'Terremoto Manabi+{k}', False)
             for k in range(1, 10)]
    rows += [('2014-06-12', 'Event', 'National', 'Ecuador', 'Inauguracion Mundial de futbol Brasil', False),
             ('2014-07-13', 'Event', 'National', 'Ecuador', 'Mundial de futbol Brasil: Final', False)]
    frame = build_holidays_frame(raw(*rows))
    quake = frame[frame.holiday == EARTHQUAKE]
    assert len(quake) == 1 and quake.iloc[0].ds == pd.Timestamp('2016-04-16') and quake.iloc[0].upper_window == 9
    cup = frame[frame.holiday == WORLD_CUP]
    assert len(cup) == 1 and cup.iloc[0].upper_window == 31
    assert set(frame.holiday) == {EARTHQUAKE, WORLD_CUP}


def test_regional_and_local_ignored():
    frame = build_holidays_frame(raw(
        ('2015-01-01', 'Holiday', 'Local', 'Quito', 'Fundacion de Quito', False),
        ('2015-01-02', 'Holiday', 'Regional', 'Imbabura', 'Provincializacion', False),
    ))
    assert frame.empty


def test_empty_input():
    assert build_holidays_frame(None).empty
