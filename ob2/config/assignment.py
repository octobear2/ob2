from dateutil import parser as DateParser
from datetime import timedelta

class AssignmentStudentView(object):
    def __init__(self, login, assignment, exceptions=None):
        self.login = login
        self.assignment = assignment

    def __getattr__(self, key):
        if self.exceptions is not None:
            for exception in self.exceptions:
                if key in exception:
                    return exception[key]
        return getattr(self.assignment, key)

class Assignment(object):
    schema = [("name", str),
              ("full_score", float),
              ("min_score", float),
              ("max_score", float),
              ("weight", float),
              ("category", str),
              ("is_group", int),
              ("manual_grading", int),
              ("not_visible_before", str),
              ("start_auto_building", str),
              ("end_auto_building", str),
              ("due_date", str),
              ("cannot_build_after", str)]

    _index_by_key = {key: index for index, (key, _) in enumerate(schema)}

    def __init__(self, *args, **kwargs):
        assert len(args) <= len(self.schema)
        args = list(args) + [None] * (len(self.schema) - len(args))
        for key, value in kwargs.items():
            # Ignore exceptions in config.yaml
            if key == "exceptions":
                continue
            args[self._index_by_key[key]] = value
        self.args = args

        # Some basic validation for assignments
        assert self.min_score <= self.max_score
        assert self.name is not None
        assert self.name, "Name cannot be blank"
        assert self.full_score is not None
        assert self.weight is not None
        assert self.category is not None
        assert self.is_group is not None
        assert self.manual_grading is not None

        # Make sure the dates are parsable
        parse_time = DateParser.parse
        not_visible_before = parse_time(self.not_visible_before)
        due_date = parse_time(self.due_date)
        if not self.manual_grading:
            start_auto_building = parse_time(self.start_auto_building)
            end_auto_building = parse_time(self.end_auto_building)
            cannot_build_after = parse_time(self.cannot_build_after)
            assert (not_visible_before <= start_auto_building <= end_auto_building <=
                    cannot_build_after)

    def __getattr__(self, key):
        return self.args[self._index_by_key[key]]

    def student_view(self, c, login):
        c.execute("SELECT days FROM extensions WHERE user = ? AND assignment = ?", [login, self.name])
        extensions = c.fetchall()
        max_days = 0
        for days in extensions:
            max_days = max(max_days, int(days))

        extend_by = timedelta(days=max_days)

        exceptions = {}
        parse_time = DateParser.parse

        due_date = parse_time(self.due_date) + extend_by
        end_auto_building = parse_time(self.end_auto_building) + extend_by
        cannot_build_after = parse_time(self.cannot_build_after) + extend_by
        
        time_format = "%b %-d %-I:%-M%p"
        exceptions["due_date"] = due_date.strftime(time_format)
        exceptions["end_auto_building"] = end_auto_building.strftime(time_format)
        exceptions["cannot_build_after"] = cannot_build_after.strftime(time_format)

        return AssignmentStudentView(login, self, exceptions=exceptions)

    def get_student_attr(self, c, student, key):
        return getattr(self.student_view(c, student), key)

    def get_fields(self):
        return self.args[:]
