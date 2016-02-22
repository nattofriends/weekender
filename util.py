# -*- cofding: utf-8 -*-
from datetime import date
from datetime import time
from datetime import timedelta
from json import JSONEncoder
import re


def flatten(lol):
    return [item for lst in lol for item in lst]


def parse_date(date_string):
    if not date_string:
        return None

    m = re.match("(\d{4})(\d{2})(\d{2})", date_string)
    if m is None:
        return None

    try:
        date_obj = date(*map(int, m.groups()))
        return date_obj
    except ValueError:
        return None


DAY_STRINGS = [
    'mon',
    'tue',
    'wed',
    'thu',
    'fri',
    'sat',
    'sun',
]

def days_string_to_dow(days_string):
    return [
        DAY_STRINGS.index(
            day.strip().lower()
        ) for day in
        days_string.strip().split(',')
    ]


def bound_weekend(weekend_date, config):
    """Return the bounding days of a weekend, subject to configuration,
    in the format ((origin_day_1, origin_day_2), (return_day_1, return_day_2))
    """
    sat_dow = DAY_STRINGS.index('sat')
    # Offset days from Saturday
    origin_days = [
        timedelta(days=(dow - sat_dow)) for dow in
        days_string_to_dow(
            config['general']['origin_days'],
        )
    ]

    return_days = [
        timedelta(days=(dow + (7 - sat_dow)) % 7) for dow in
        days_string_to_dow(
            config['general']['return_days'],
        )
    ]

    if not weekend_date:
        return (None, None)

    # The datepicker is set up to allow picking Saturday and Sunday
    dow = weekend_date.weekday()
    if dow not in (5, 6):
        return (None, None)
    elif dow == 6:
        weekend_date -= timedelta(days=1)

    return (
        [weekend_date + day for day in origin_days],
        [weekend_date + day for day in return_days],
    )

def tomorrow(date_obj):
    return date_obj + timedelta(days=1)


def meridian(hour, indicator):
    if indicator == "AM" and hour == 12:
        hour = 0
    if indicator == "PM" and hour < 12:
        hour += 12

    return hour


class WeekenderEncoder(JSONEncoder):

    def default(self, obj):
        if isinstance(obj, date):
            # Yes, this is not the representation that comes in.
            return obj.strftime('%a %Y/%m/%d')
        if isinstance(obj, time):
            return obj.strftime('%-I:%M %p')
        # Let the base class default method raise the TypeError
        return super(WeekenderEncoder, self).default(obj)
