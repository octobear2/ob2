import numpy as np
from math import ceil, floor

from ob2.util.config_data import get_assignment_by_name
from ob2.util.time import format_js_compatible_time, now, parse_time
from ob2.util.build_constants import SUCCESS


class Datasets(object):
    """
    A collection of useful dataset generators. Each dataset should take a database cursor as its
    first argument, followed by the arguments of the dataset itself.

    The return value of each dataset will be None if the arguments do not lead to a valid dataset.

    """

    @classmethod
    def grade_distribution(cls, c, assignment_name, max_bins=None):
        """
        Returns a pre-binned histogram of grades for the assignment. Here is an example of what the
        data looks like:

            [{'x': 0, 'dx': 1, 'y': 3},
             {'x': 1, 'dx': 2, 'y': 0},
             {'x': 2, 'dx': 3, 'y': 0},
             {'x': 3, 'dx': 4, 'y': 0},
             {'x': 4, 'dx': 5, 'y': 1},
             {'x': 5, 'dx': 6, 'y': 2},
             {'x': 6, 'dx': 7, 'y': 5},
             {'x': 7, 'dx': 8, 'y': 11},
             {'x': 8, 'dx': 9, 'y': 7},
             {'x': 9, 'dx': 10, 'y': 15},
             {'x': 10, 'dx': 11, 'y': 35},
             {'x': 11, 'dx': 12, 'y': 92}]

        """
        assignment = get_assignment_by_name(assignment_name)
        if not assignment:
            return
        grade_set = cls._get_grade_set(c, assignment.name)
        if not grade_set:
            return []
        grade_set_min, grade_set_max = min(grade_set), max(grade_set)
        assignment_min, assignment_max = assignment.min_score, assignment.full_score
        bin_min = int(floor(min(grade_set_min, assignment_min)))
        bin_max = int(ceil(max(grade_set_max, assignment_max)))
        bin_range = bin_max - bin_min

        if max_bins is None:
            if len(str(bin_max)) < 3:
                max_bins = 16
            elif len(str(bin_max)) < 4:
                max_bins = 13
            elif len(str(bin_max)) < 5:
                max_bins = 10
            else:
                max_bins = 7

        # The minimum number of bins for factorizable ranges.
        # Does not apply when range < max_bins.
        min_bins = max_bins / 2

        # How flexible is the max_bins? We'll allow this many more bins.
        flexibility = 1.8

        def factorize(n):
            for candidate in range(2, n):
                if n % candidate == 0:
                    return [candidate] + factorize(n / candidate)
            return [n]

        if bin_range <= max_bins:
            per_bin = 1.0
            num_bins = bin_range
        else:
            factorization = factorize(bin_range)
            per_bin = 1
            for factor in factorization:
                if per_bin * factor * min_bins > bin_range:
                    break
                else:
                    per_bin *= factor
                    if per_bin * max_bins > bin_range:
                        break
            if per_bin * max_bins * flexibility > bin_range:
                num_bins = bin_range / per_bin
                per_bin = float(per_bin)
            else:
                # The best per_bin is too small to look good.
                # So just fallback to naive division method.
                num_bins = max_bins
                per_bin = float(bin_range) / max_bins
        boundaries = [int(round(per_bin * n)) for n in range(1, num_bins)]
        bin_sizes = [0] * num_bins
        for score in grade_set:
            bin_index = int(floor((score - bin_min) / per_bin))
            if bin_index >= num_bins:
                bin_index = num_bins - 1
            bin_sizes[bin_index] += 1
        return [{"x": x, "dx": dx, "y": y}
                for x, dx, y in zip([bin_min] + boundaries,
                                    boundaries + [bin_max],
                                    bin_sizes)]

    @staticmethod
    def timeseries_grade_percentiles(c, assignment_name, num_points=40):
        """
        Returns a timeseries of grades with percentiles. Here is an example:

            [["2015-07-17 19:00:36-0700", 0.0, 0.0, 0.0, ... 0.0, 0.0],
             ["2015-07-17 19:10:36-0700", 0.0, 0.0, 0.0, ... 1.0, 2.0],
             ["2015-07-17 19:20:36-0700", 0.0, 0.0, 0.0, ... 3.0, 4.0],
             ["2015-07-17 19:30:36-0700", 0.0, 0.0, 0.5, ... 5.0, 6.0],
             ["2015-07-17 19:40:36-0700", 0.0, 0.0, 1.0, ... 7.0, 8.0]]

        """
        data_keys = range(0, 105, 5)
        assignment = get_assignment_by_name(assignment_name)
        if not assignment:
            return
        # There is a slight problem that because of DST, ordering by "started" may not always
        # produce the correct result. When the timezone changes, lexicographical order does not
        # match the actual order of the times. However, this only happens once a year in the middle
        # of the night, so fuck it.
        c.execute('''SELECT source, score, started FROM builds WHERE job = ? AND status = ?
                     ORDER BY started''', [assignment_name, SUCCESS])
        # XXX: There is no easy way to exclude builds started by staff ("super") groups.
        # But because this graph is to show the general trend, it's usually fine if staff builds
        # are included. Plus, the graph only shows up in the admin interface anyway.
        builds = [(source, score, parse_time(started)) for source, score, started in c.fetchall()]
        if not builds:
            return []
        source_set = map(lambda b: b[0], builds)
        started_time_set = map(lambda b: b[2], builds)
        min_started = min(started_time_set)
        max_started = max(started_time_set)
        assignment_min_started = parse_time(assignment.not_visible_before)
        assignment_max_started = parse_time(assignment.due_date)
        data_min = min(min_started, assignment_min_started)
        data_max = max(max_started, assignment_max_started)
        data_points = []
        best_scores_so_far = {source: 0 for source in source_set}
        time_delta = (data_max - data_min) / (num_points - 1)
        current_time = data_min
        for source, score, started_time in builds:
            while current_time < started_time:
                percentiles = np.percentile(best_scores_so_far.values(), data_keys)
                data_points.append([format_js_compatible_time(current_time)] + list(percentiles))
                current_time += time_delta
            if score is not None:
                best_scores_so_far[source] = max(score, best_scores_so_far[source])

        percentiles = list(np.percentile(best_scores_so_far.values(), data_keys))
        now_time = now()
        while current_time - (time_delta / 2) < data_max:
            data_points.append([format_js_compatible_time(current_time)] + percentiles)
            if current_time >= now_time:
                percentiles = [None] * len(percentiles)
            current_time += time_delta

        return data_points

    @staticmethod
    def _get_grade_set(c, assignment_name):
        """A helper function to get all the non-null grades for an assignment."""
        c.execute('''SELECT grades.score FROM grades LEFT JOIN users ON grades.user = users.id
                     WHERE grades.assignment = ? AND grades.score IS NOT NULL AND
                     users.super = 0''',
                  [assignment_name])
        return [score for score, in c.fetchall()]
