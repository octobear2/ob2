import ob2.config as config
from ob2.util.time import now_compare, parse_time

_assignment_name_set = None


def get_assignment_name_set():
    global _assignment_name_set
    if _assignment_name_set is None:
        _assignment_name_set = {assignment.name for assignment in config.assignments}
    return _assignment_name_set
