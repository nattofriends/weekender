# -*- cofding: utf-8 -*-
from datetime import date
from datetime import time
from datetime import timedelta
from json import JSONEncoder
import re

ONE = timedelta(days=1)
TWO = timedelta(days=2)

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


def bound_weekend(weekend_date):
    """Return the bounding days of a weekend (Friday and Sunday)."""

    if not weekend_date:
        return (None, None)


    # The datepicker is set up to allow picking Saturday and Sunday
    dow = weekend_date.weekday()
    if dow not in (5, 6):
        return (None, None)
    elif dow == 5:
        begin = weekend_date - ONE
        end = weekend_date + ONE
    elif dow == 6:
        begin = weekend_date - TWO
        end = weekend_date

    return (begin, end)


def tomorrow(date_obj):
    return date_obj + ONE


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
            return obj.strftime('%Y/%m/%d')
        if isinstance(obj, time):
            return obj.strftime('%I:%M %p')
        # Let the base class default method raise the TypeError
        return super(WeekenderEncoder, self).default(obj)
