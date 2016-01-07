import pytz
from datetime import datetime
from dateutil import parser as DateParser
from math import ceil

import ob2.config as config


def now():
    """Gets the current datetime (with timezone) as an object."""
    timezone_obj = pytz.timezone(config.timezone)
    return datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(timezone_obj)


def now_str():
    """Gets the current datetime in a serializable format (for database)."""
    return format_time(now())


def format_time(s):
    """Converts a datetime object to serializable format."""
    return s.isoformat()


def format_js_compatible_time(s):
    """Converts a datetime object to serializable format for JavaScript."""
    return s.strftime("%Y-%m-%dT%H:%M:%S%z")


def parse_time(s):
    """Converts serializable datetime to a datetime object."""
    return DateParser.parse(s)


def slip_units(due_date, submit_date):
    """Computes the number of slip units (see ob2.config) between the due date and submit_date."""
    if isinstance(due_date, basestring):
        due_date = parse_time(due_date)
    if isinstance(submit_date, basestring):
        submit_date = parse_time(submit_date)
    lateness = submit_date - due_date
    total_seconds = lateness.total_seconds() - config.slip_grace_period
    if total_seconds <= 0:
        return 0
    else:
        return int(ceil(float(total_seconds) / config.slip_seconds_per_unit))


def slip_units_now(due_date):
    """Computes the number of slip units (see ob2.config) between the due date and now()."""
    return slip_units(due_date, now())


def now_compare(start_date, end_date=None):
    """
    Given (start_date, end_date), return -1 if now() is before start_date
                                  return  1 if now() is after end_date
                                  return  0 if now() is between start_date and end_date inclusive.

    If end_date is ommitted, it takes the same value as start_date.

    """
    if isinstance(start_date, basestring):
        start_date = parse_time(start_date)
    if end_date is None:
        end_date = start_date
    if isinstance(end_date, basestring):
        end_date = parse_time(end_date)
    current_date = now()
    if current_date < start_date:
        return -1
    elif current_date <= end_date:
        return 0
    else:
        return 1


def parse_to_relative(target, past_relative_cutoff=86400, future_relative_cutoff=-86400):
    """
    Expresses TARGET as it is relative to now(). If the target is more than Y seconds in the past
    or more than Z seconds in the future, then express TARGET in an absolute way.

    """
    if isinstance(target, basestring):
        target = parse_time(target)
    delta = now() - target
    total_seconds = delta.total_seconds()
    # Example: Jul 9 8:00PM
    extended_date_format = "%b %-d %-I:%M%p"
    if total_seconds < -6 * 30.5 * 86400 or total_seconds > 6 * 30.5 * 86400:
        extended_date_format += " %Y"
    if total_seconds > past_relative_cutoff or total_seconds < -abs(future_relative_cutoff):
        return target.strftime(extended_date_format)
    return delta_to_relative(total_seconds)


def delta_to_relative(delta_seconds):
    if 0 <= delta_seconds < 60:
        return "Just now"
    elif 60 <= delta_seconds < 120:
        return "1 minute ago"
    elif 120 <= delta_seconds < 3600:
        return "%d minutes ago" % (delta_seconds / 60)
    elif 3600 <= delta_seconds < 7200:
        return "1 hour ago"
    elif 7200 <= delta_seconds < 86400:
        return "%d hours ago" % (delta_seconds / 3600)
    elif 86400 <= delta_seconds < 2 * 86400:
        return "1 day ago"
    elif 2 * 86400 <= delta_seconds < 30.5 * 86400:
        return "%d days ago" % (delta_seconds / 86400)
    elif 30.5 * 86400 <= delta_seconds < 61 * 86400:
        return "1 month ago"
    elif 61 * 86400 <= delta_seconds < 365 * 86400:
        return "%d months ago" % (delta_seconds / (30.5 * 86400))
    elif 365 * 86400 <= delta_seconds < 2 * 365 * 86400:
        return "1 year ago"
    elif 2 * 365 * 86400 <= delta_seconds:
        return "%d years ago" % (delta_seconds / (365.25 * 86400))
    elif 0 > delta_seconds >= -1:
        return "1 second from now"
    elif -1 > delta_seconds > -60:
        return "%d seconds from now" % (-delta_seconds)
    elif -60 >= delta_seconds > -120:
        return "1 minute from now"
    elif -120 >= delta_seconds > -3600:
        return "%d minutes from now" % (-delta_seconds / 60)
    elif -3600 >= delta_seconds > -7200:
        return "1 hour from now"
    elif -3600 >= delta_seconds > -86400:
        return "%d hours from now" % (-delta_seconds / 3600)
    elif -86400 >= delta_seconds > -2 * 86400:
        return "1 day from now"
    elif -2 * 86400 >= delta_seconds > -30.5 * 86400:
        return "%d days from now" % (-delta_seconds / 86400)
    elif -30.5 * 86400 >= delta_seconds > -61 * 86400:
        return "1 month from now"
    elif -61 * 86400 >= delta_seconds > -365 * 86400:
        return "%d months from now" % (-delta_seconds / (30.5 * 86400))
    elif -365 * 86400 >= delta_seconds > -2 * 365 * 86400:
        return "1 year from now"
    elif -2 * 365 * 86400 >= delta_seconds:
        return "%d years from now" % (-delta_seconds / (365.25 * 86400))
    else:
        return ''
