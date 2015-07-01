"""
Time related utilities and helper functions.
"""

import datetime


# ISO 8601 extended time format with microseconds
_ISO8601_TIME_FORMAT_SUBSECOND = '%Y-%m-%dT%H:%M:%S.%f'
_ISO8601_TIME_FORMAT = '%Y-%m-%dT%H:%M:%S'
PERFECT_TIME_FORMAT = _ISO8601_TIME_FORMAT_SUBSECOND


def strtime(at=None, fmt=PERFECT_TIME_FORMAT):
    """Returns formatted utcnow."""
    if not at:
        at = utcnow()
    return at.strftime(fmt)


def parse_strtime(timestr, fmt=PERFECT_TIME_FORMAT):
    """Turn a formatted time back into a datetime."""
    return datetime.datetime.strptime(timestr, fmt)


def normalize_time(timestamp):
    """Normalize time in arbitrary timezone to UTC naive object."""
    offset = timestamp.utcoffset()
    if offset is None:
        return timestamp
    return timestamp.replace(tzinfo=None) - offset


def utcnow():
    """
    Overridable version of utils.utcnow.
    """
    if utcnow.override_time:
        try:
            return utcnow.override_time.pop(0)
        except AttributeError:
            return utcnow.override_time
    return datetime.datetime.utcnow()


utcnow.override_time = None

def delta_seconds(before, after):
    """
    Return the difference between two timing objects.
    """
    delta = after - before
    return total_seconds(delta)


def total_seconds(delta):
    """
    Return the total seconds of datetime.timedelta object.
    """
    try:
        return delta.total_seconds()
    except AttributeError:
        return ((delta.days * 24 * 3600) + delta.seconds +
                float(delta.microseconds) / (10 ** 6))


def is_soon(dt, window):
    """
    Determines if time is going to happen in the next window seconds.
    """
    soon = (utcnow() + datetime.timedelta(seconds=window))
    return normalize_time(dt) <= soon
