from dateutil import parser as DateParser


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
        parse_time(self.due_date)
        if not self.manual_grading:
            start_auto_building = parse_time(self.start_auto_building)
            end_auto_building = parse_time(self.end_auto_building)
            cannot_build_after = parse_time(self.cannot_build_after)
            assert (not_visible_before <= start_auto_building <= end_auto_building <=
                    cannot_build_after)

    def __getattr__(self, key):
        return self.args[self._index_by_key[key]]

    def get_fields(self):
        return self.args[:]
