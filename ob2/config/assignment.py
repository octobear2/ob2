from dateutil import parser as DateParser

class AssignmentStudentView(object):
    def __init__(self, login, assignment):
        self.login = login
        self.assignment = assignment

    def __getattr__(self, key):
        if self.assignment.exceptions is not None:
            if self.login in self.assignment.exceptions:
                if key in self.assignment.exceptions[self.login]:
                    return self.assignment.exceptions[self.login][key]
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
              ("cannot_build_after", str),
              ("exceptions", dict)]

    _index_by_key = {key: index for index, (key, _) in enumerate(schema)}

    def __init__(self, *args, **kwargs):
        assert len(args) < len(self.schema)
        args = list(args) + [None] * (len(self.schema) - len(args))
        for key, value in kwargs.items():
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
            if self.exceptions is not None:
                exception_not_visible_before = not_visible_before
                exception_due_date = due_date
                exception_start_auto_building = start_auto_building
                exception_end_auto_building = end_auto_building
                exception_cannot_build_after = cannot_build_after
                for _, exception in self.exceptions.items():
                    if "not_visible_before" in exception:
                        exception_not_visible_before = parse_time(exception["not_visible_before"])
                    if "due_date" in exception:
                        exception_due_date = parse_time(exception["due_date"])
                    if "start_auto_building" in exception:
                        exception_start_auto_building = parse_time(exception["start_auto_building"])
                    if "end_auto_building" in exception:
                        exception_end_auto_building = parse_time(exception["end_auto_building"])
                    if "cannot_build_after" in exception:
                        exception_cannot_build_after = parse_time(exception["cannot_build_after"])
                    assert (exception_not_visible_before <= exception_start_auto_building <=
                            exception_end_auto_building <= exception_cannot_build_after)

    def __getattr__(self, key):
        return self.args[self._index_by_key[key]]

    def student_view(self, login):
        return AssignmentStudentView(login, self)

    def get_student_attr(self, student, key):
        return getattr(self.student_view(student), key)

    def get_fields(self):
        return self.args[:]
