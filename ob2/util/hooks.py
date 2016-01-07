import logging
from collections import defaultdict

LOG = logging.getLogger()
_HOOKS_ACTIONS = defaultdict(list)
_HOOKS_FILTERS = defaultdict(list)
_HOOKS_PARTIALS = defaultdict(list)
_HOOKS_JOBS = {}


def register_action(name, priority=10):
    """
    Registers a function that is called at a particular place in the code.
    The function's arguments should match the corresponding to do_action() in the code.

        name     -- The name of the action
        priority -- A priority value (lower numbered priority functions are run first)

    This function is NOT thread safe. (But that's okay, because hooks are supposed to be registered
    at import-time.)

    """
    def decorator(fn):
        _HOOKS_ACTIONS[name].append((priority, fn))
        _HOOKS_ACTIONS[name] = sorted(_HOOKS_ACTIONS[name])
        LOG.info("New action handler %s for %s" % (repr(fn.__name__), repr(name)))
        return fn

    return decorator


def do_action(name, *args):
    """
    Runs all functions registered under NAME.

    """
    for _, hook in _HOOKS_ACTIONS[name]:
        hook(*args)


def register_filter(name, priority=10):
    """
    Registers a function that is modifies a particular value in the code.
    The function's arguments should match the corresponding to apply_filters() in the code.

        name     -- The name of the filter
        priority -- A priority value (lower numbered priority functions are called first)

    This function is NOT thread safe. (But that's okay, because hooks are supposed to be registered
    at import-time.)

    """
    def decorator(fn):
        _HOOKS_FILTERS[name].append((priority, fn))
        _HOOKS_FILTERS[name] = sorted(_HOOKS_FILTERS[name])
        LOG.info("New filter function %s for %s" % (repr(fn.__name__), repr(name)))
        return fn

    return decorator


def apply_filters(name, value, *args):
    """
    Applies all filters registered under NAME to VALUE.

    """
    for _, hook in _HOOKS_FILTERS[name]:
        value = hook(value, *args)
    return value


def register_partial(name, priority=10):
    """
    Registers a function that is interpolated into a template.
    The function's arguments should match the corresponding to show_partial() in the code.

        name     -- The name of the partial
        priority -- A priority value (lower numbered priority functions are displayed first)

    This function is NOT thread safe. (But that's okay, because hooks are supposed to be registered
    at import-time.)

    """
    def decorator(fn):
        _HOOKS_PARTIALS[name].append((priority, fn))
        _HOOKS_PARTIALS[name] = sorted(_HOOKS_PARTIALS[name])
        LOG.info("New partial %s for %s" % (repr(fn.__name__), repr(name)))
        return fn

    return decorator


def show_partial(name, *args):
    """
    Returns all partials registered under NAME.
    This function should be used in templates (see jinja_show_partial).

    """
    return "".join(map(str, [hook(*args) for _, hook in _HOOKS_PARTIALS[name]]))


def register_job(name):
    """
    Registers a job handler that is used in dockergrader. Replaces any job handler that was
    previously registered with the same job.
    The function's arguments should be (repo_name, commit_hash), and the function should return
    (build_log, score).

        name -- The name of the job

    This function is NOT thread safe. (But that's okay, because hooks are supposed to be registered
    at import-time.)

    """
    def decorator(fn):
        _HOOKS_JOBS[name] = fn
        LOG.info("New job handler registered for %s" % repr(name))
        return fn

    return decorator


def get_job(name):
    """
    Returns the job handler registered for NAME. If no job handler is registered, raises KeyError.
    This function should only be used by ob2.dockergrader.worker.

    """
    return _HOOKS_JOBS[name]
