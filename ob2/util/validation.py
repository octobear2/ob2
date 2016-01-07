from flask import flash, redirect


def float_or_none(s):
    if not s:
        return None
    else:
        return float(s)


def int_or_none(s):
    if not s:
        return None
    else:
        return int(s)


def same_length(*args):
    lengths = map(len, args)
    return len(set(lengths)) < 2


class ValidationError(Exception):
    def __init__(self, message, category="error"):
        super(ValidationError, self).__init__()
        self.args = (message, category)


def fail_validation(message, category="error"):
    raise ValidationError(message, category)


def redirect_with_error(target, e):
    message, category = e.args
    flash(message, category)
    return redirect(target)
