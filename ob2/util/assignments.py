import ob2.config as config
from ob2.util.time import now_compare, parse_time

_assignment_name_set = None


def get_assignment_name_set():
    global _assignment_name_set
    if _assignment_name_set is None:
        _assignment_name_set = {assignment.name for assignment in config.assignments}
    return _assignment_name_set


def has_build_exception(assignment, login):
    """
    Returns True if the login has a build exception for the given assignment.
    Build exceptions allow the user to build even after the cannot_build_after deadline.
    """
    build_exceptions = assignment.build_exception
    if build_exceptions is None:
        return False
    if login in build_exceptions:
        exception_policy = build_exceptions[login]
        if "start" not in exception_policy:
            start = assignment.start_auto_building
        else:
            start = parse_time(exception_policy["start"])
        if "end" not in exception_policy:
            end = assignment.cannot_build_after
        else:
            end = parse_time(exception_policy["end"])
        return now_compare(start, end) == 0
    return False
