import datetime
import pytz
from mock import patch
from unittest2 import TestCase

from ob2.util.time import (
    now_str,
    format_time,
    parse_time,
    parse_to_relative,
)


class TestTime(TestCase):
    def test_time_functions(self):
        timestamp_str = now_str()
        timestamp_obj = parse_time(timestamp_str)
        self.assertEqual(timestamp_str, format_time(timestamp_obj))

    @patch("ob2.util.time.now",
           lambda: datetime.datetime(2015, 7, 4, 0, 0, 0).replace(tzinfo=pytz.utc))
    def test_parse_to_relative(self):
        """Tests parse_to_relative and delta_to_relative various formats."""

        kw = {"past_relative_cutoff": 999999999999,
              "future_relative_cutoff": -999999999999}
        self.assertEqual("Just now", parse_to_relative("Jul 3 2015 23:59:59 UTC"))
        self.assertEqual("Just now", parse_to_relative("Jul 4 2015 00:00:00 UTC"))
        self.assertEqual("1 second from now", parse_to_relative("Jul 4 2015 00:00:01 UTC"))
        self.assertEqual("5 seconds from now", parse_to_relative("Jul 4 2015 00:00:05 UTC"))

        self.assertEqual("Just now", parse_to_relative("Jul 3 2015 23:59:01 UTC"))
        self.assertEqual("1 minute ago", parse_to_relative("Jul 3 2015 23:59:00 UTC"))
        self.assertEqual("1 minute ago", parse_to_relative("Jul 3 2015 23:58:59 UTC"))
        self.assertEqual("1 minute ago", parse_to_relative("Jul 3 2015 23:58:01 UTC"))
        self.assertEqual("2 minutes ago", parse_to_relative("Jul 3 2015 23:58:00 UTC"))
        self.assertEqual("59 minutes ago", parse_to_relative("Jul 3 2015 23:00:01 UTC"))
        self.assertEqual("1 hour ago", parse_to_relative("Jul 3 2015 23:00:00 UTC"))
        self.assertEqual("1 hour ago", parse_to_relative("Jul 3 2015 22:00:01 UTC"))
        self.assertEqual("2 hours ago", parse_to_relative("Jul 3 2015 22:00:00 UTC"))
        self.assertEqual("23 hours ago", parse_to_relative("Jul 3 2015 00:00:01 UTC", **kw))
        self.assertEqual("1 day ago", parse_to_relative("Jul 3 2015 00:00:00 UTC", **kw))
        self.assertEqual("1 day ago", parse_to_relative("Jul 2 2015 00:00:01 UTC", **kw))
        self.assertEqual("2 days ago", parse_to_relative("Jul 2 2015 00:00:00 UTC", **kw))
        self.assertEqual("1 month ago", parse_to_relative("Jun 2 2015 00:00:00 UTC", **kw))
        self.assertEqual("5 months ago", parse_to_relative("Jan 20 2015 00:00:00 UTC", **kw))
        self.assertEqual("10 months ago", parse_to_relative("Aug 20 2014 00:00:00 UTC", **kw))
        self.assertEqual("11 months ago", parse_to_relative("Jul 20 2014 00:00:10 UTC", **kw))
        self.assertEqual("1 year ago", parse_to_relative("Jun 20 2014 00:00:10 UTC", **kw))
        self.assertEqual("1 year ago", parse_to_relative("Jul 20 2013 00:00:10 UTC", **kw))
        self.assertEqual("2 years ago", parse_to_relative("Jun 20 2013 00:00:10 UTC", **kw))

        self.assertEqual("59 seconds from now", parse_to_relative("Jul 4 2015 00:00:59 UTC"))
        self.assertEqual("1 minute from now", parse_to_relative("Jul 4 2015 00:01:00 UTC"))
        self.assertEqual("1 minute from now", parse_to_relative("Jul 4 2015 00:01:59 UTC"))
        self.assertEqual("2 minutes from now", parse_to_relative("Jul 4 2015 00:02:00 UTC"))
        self.assertEqual("59 minutes from now", parse_to_relative("Jul 4 2015 00:59:59 UTC"))
        self.assertEqual("1 hour from now", parse_to_relative("Jul 4 2015 01:00:00 UTC"))
        self.assertEqual("1 hour from now", parse_to_relative("Jul 4 2015 01:59:59 UTC"))
        self.assertEqual("2 hours from now", parse_to_relative("Jul 4 2015 02:00:00 UTC"))
        self.assertEqual("23 hours from now", parse_to_relative("Jul 4 2015 23:59:59 UTC", **kw))
        self.assertEqual("1 day from now", parse_to_relative("Jul 5 2015 00:00:00 UTC", **kw))
        self.assertEqual("1 day from now", parse_to_relative("Jul 5 2015 23:59:59 UTC", **kw))
        self.assertEqual("2 days from now", parse_to_relative("Jul 6 2015 00:00:00 UTC", **kw))
        self.assertEqual("1 month from now", parse_to_relative("Aug 6 2015 00:00:00 UTC", **kw))
        self.assertEqual("2 months from now", parse_to_relative("Sep 6 2015 00:00:00 UTC", **kw))
        self.assertEqual("11 months from now", parse_to_relative("Jun 20 2016 00:00:00 UTC", **kw))
        self.assertEqual("1 year from now", parse_to_relative("Jul 20 2016 00:00:00 UTC", **kw))
        self.assertEqual("1 year from now", parse_to_relative("Jun 20 2017 00:00:00 UTC", **kw))
        self.assertEqual("2 years from now", parse_to_relative("Jul 20 2017 00:00:00 UTC", **kw))

        kw = {"past_relative_cutoff": 3600,
              "future_relative_cutoff": -86400}
        self.assertEqual("23 hours from now", parse_to_relative("Jul 4 2015 23:59:59 UTC", **kw))
        self.assertEqual("Jul 5 12:00AM", parse_to_relative("Jul 5 2015 00:00:01 UTC", **kw))
        self.assertEqual("59 minutes ago", parse_to_relative("Jul 3 2015 23:00:01 UTC", **kw))
        self.assertEqual("Jul 3 10:59PM", parse_to_relative("Jul 3 2015 22:59:59 UTC", **kw))
