from ansi2html import Ansi2HTMLConverter
from binascii import b2a_base64
from markupsafe import Markup

import ob2.config as config
from ob2.util.build_constants import (
    QUEUED,
    IN_PROGRESS,
    SUCCESS,
    FAILED,
    build_status_to_string,
)
from ob2.util.encoding import wrangle_to_unicode
from ob2.util.group_constants import (
    INVITED,
    ACCEPTED,
    REJECTED,
    invitation_status_to_string,
)
from ob2.util.hooks import apply_filters, show_partial
from ob2.util.security import generate_csrf_token
from ob2.util.time import now_compare, parse_to_relative

_github_base = "https://github.com/%s"


def github_user_url(username):
    return _github_base % (username)


def github_repo_name(repo):
    return "%s/%s" % (config.github_organization, repo)


def github_repo_url(repo):
    return _github_base % ("%s/%s" % (config.github_organization, repo))


def github_commit_url(repo, commit):
    return _github_base % ("%s/%s/commit/%s" % (config.github_organization, repo, commit))


def score_color(score, full_score):
    if score == full_score:
        return "#44AA00"
    else:
        return "#AA4400"


def status_color(status):
    if status == QUEUED:
        return "#4400AA"
    elif status == IN_PROGRESS:
        return "#0044AA"
    elif status == FAILED:
        return "#AA4400"
    elif status == SUCCESS:
        return "#44AA00"
    else:
        return "#000000"


def status_bar(score, full_score=1, size=100):
    fraction = float(score) / full_score
    if fraction > 1.0:
        fraction = 1.0
    if fraction < 0.0:
        fraction = 0.0
    return ('''
        <span style="display: block;
                     float: left;
                     margin-right: -%dpx;
                     position: relative;
                     top: 8px;">''' +
            '''<span style="display: inline-block;
                            width: %dpx;
                            height: 2px;
                            background: #44AA00;"></span>''' +
            '''<span style="display: inline-block;
                            width: %dpx;
                            height: 2px;
                            background: #AA4400;"></span>''' +
            '''</span>''') % (size, round(fraction * size), round((1 - fraction) * size))


def slip_unit_name(n=0):
    if n == 1:
        return config.slip_unit_name_singular
    else:
        return config.slip_unit_name_plural


def invitation_status(status):
    color = {
        ACCEPTED: "green",
        INVITED: "purple",
        REJECTED: "red",
    }
    return '''<span class="mdl-color-text--%s-800" style="padding-left: 10px;
                           float: right;">%s</span>''' % (
           color.get(status, "black"), invitation_status_to_string(status))


def list_conjunction(n, length):
    if length == 1 or n == 0:
        return " "
    elif length == 2:
        return " and "
    elif n == length - 1:
        return ", and "
    else:
        return ", "


def flash_color(category):
    return {"error": "red",
            "success": "green"}.get(category, "red")


def assignment_status(manual_grading, not_visible_before, cannot_build_after):
    is_visible = now_compare(not_visible_before) >= 0
    if not is_visible:
        return ("purple", "Hidden")
    elif manual_grading:
        return ("grey", "Visible")

    can_build = now_compare(cannot_build_after) <= 0
    if not can_build:
        return ("grey", "Finished")
    else:
        return ("green", "Ongoing")


def auto_build_status(manual_grading, begin, end):
    if manual_grading:
        return ("grey", "Manual Grading")
    status = now_compare(begin, end)
    if status == 0:
        return ("green", "Enabled")
    elif status == -1:
        return ("purple", "Not yet enabled")
    else:
        return ("grey", "Disabled")


def participation_color(amount):
    if amount == 0.0:
        return "grey"
    elif amount < 0.4:
        return "red"
    elif amount < 0.75:
        return "amber"
    else:
        return "green"


def ansi_to_html(ansi_text):
    return Ansi2HTMLConverter(inline=True).convert(wrangle_to_unicode(ansi_text), full=False)


def jinja_show_partial(name, *args, **kwargs):
    return Markup(show_partial(name, *args, **kwargs))


JINJA_EXPORTS = {
    "FAILED": FAILED,
    "IN_PROGRESS": IN_PROGRESS,
    "SUCCESS": SUCCESS,
    "build_status_to_string": build_status_to_string,
    "generate_csrf_token": generate_csrf_token,
    "github_user_url": github_user_url,
    "github_repo_name": github_repo_name,
    "github_repo_url": github_repo_url,
    "github_commit_url": github_commit_url,
    "parse_to_relative": parse_to_relative,
    "score_color": score_color,
    "status_color": status_color,
    "status_bar": status_bar,
    "slip_unit_name": slip_unit_name,
    "invitation_status": invitation_status,
    "list_conjunction": list_conjunction,
    "flash_color": flash_color,
    "assignment_status": assignment_status,
    "auto_build_status": auto_build_status,
    "participation_color": participation_color,
    "wrangle_to_unicode": wrangle_to_unicode,
    "ansi_to_html": ansi_to_html,
    "apply_filters": apply_filters,
    "show_partial": jinja_show_partial,
    "course_name": lambda: config.course_name,
    "course_number": lambda: config.course_number,
    "course_login_format": lambda login: config.course_login_format % login,
    "b2a_base64": b2a_base64,
    "student_photos_enabled": lambda: config.student_photos_enabled,
}
