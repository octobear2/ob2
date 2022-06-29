import json
from collections import OrderedDict
from flask import (Blueprint, Response, abort, g, redirect, render_template, request, session,
                   url_for)
from functools import wraps
from math import sqrt
import threading
import ctypes

import ob2.config as config
from ob2.database import DbCursor
from ob2.database.helpers import (
    create_build,
    finalize_group_if_ready,
    get_groups,
    get_grouplimit,
    get_next_autoincrementing_value,
    get_user_by_id,
    get_user_by_github,
    get_super,
    modify_grouplimit,
)
from ob2.dockergrader import dockergrader_queue, Job
from ob2.mailer import create_email, mailer_queue
from ob2.repomanager import repomanager_queue
from ob2.util.authentication import user_id
from ob2.util.config_data import get_assignment_by_name
from ob2.util.datasets import Datasets
from ob2.util.github_api import get_branch_hash, get_commit_message
from ob2.util.github_login import is_ta
from ob2.util.group_constants import ACCEPTED, INVITED, REJECTED
from ob2.util.security import require_csrf_token
from ob2.util.time import now_str, now_compare, slip_units_now, add_grace_period
from ob2.util.validation import fail_validation, ValidationError, redirect_with_error
from ob2.util.job_limiter import rate_limit_fail_build, should_limit_source

blueprint = Blueprint("dashboard", __name__, template_folder="templates")


def _get_student(c):
    if not hasattr(g, "student"):
        g.student = get_user_by_id(c, user_id())
    return g.student


def _template_common(c):
    return {"student": _get_student(c),
            "is_ta": is_ta(),
            "groups_enabled": config.groups_enabled}


def _require_login(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not user_id():
            if request.method == "GET":
                session["login_next__dashboard"] = request.base_url
            elif "login_next__dashboard" in session:
                del session["login_next__dashboard"]
            return redirect(url_for("onboarding.log_in"))
        else:
            if "login_next__dashboard" in session:
                del session["login_next__dashboard"]
            return fn(*args, **kwargs)
    return wrapped


@blueprint.route("/dashboard/")
@_require_login
def index():
    return redirect(url_for("dashboard.assignments"))


@blueprint.route("/dashboard/assignments/")
@_require_login
def assignments():
    with DbCursor() as c:
        student = _get_student(c)
        user_id, _, _, login, _, _ = student
        super_value = get_super(c, user_id)
        dropped = super_value is not None and super_value < 0
        c.execute("SELECT assignment, score, slipunits, updated FROM grades WHERE user = ?",
                  [user_id])
        grade_info = {assignment: (score, slipunits, updated)
                      for assignment, score, slipunits, updated in c.fetchall()}
        template_common = _template_common(c)
        assignments_info = []
        if not dropped:
            for assignment in config.assignments:
                a = assignment.student_view(c, login)
                if now_compare(a.not_visible_before) >= 0:
                    assignments_info.append((a.name, a.full_score, a.weight, a.due_date) +
                                grade_info.get(a.name, (None, None, None)))
    return render_template("dashboard/assignments.html",
                           assignments_info=assignments_info,
                           **template_common)


@blueprint.route("/dashboard/assignments/<name>/")
@_require_login
def assignments_one(name):
    with DbCursor() as c:
        student = _get_student(c)
        user_id, _, _, login, _, _ = student
        assignment = get_assignment_by_name(name)
        super_value = get_super(c, user_id)
        dropped = super_value is not None and super_value < 0

        if not assignment:
            abort(404)

        assignment = assignment.student_view(c, login)

        slipunits_now = slip_units_now(assignment.due_date)
        is_visible = now_compare(assignment.not_visible_before) >= 0 and not dropped
        if assignment.manual_grading:
            can_build = False
        else:
            can_build = now_compare(add_grace_period(assignment.cannot_build_after)) <= 0
        manual_grading = assignment.manual_grading

        if not is_visible:
            abort(404)

        c.execute("SELECT score, slipunits, updated FROM grades WHERE user = ? AND assignment = ?",
                  [user_id, name])
        grade = c.fetchone()
        if not grade:
            grade = (None, None, None)
        if assignment.is_group:
            repos = get_groups(c, user_id)
        else:
            repos = [login]
        c.execute('''SELECT build_name, source, status, score, `commit`, message, started
                     FROM builds WHERE job = ? AND source IN (%s)
                     ORDER BY started DESC''' % (",".join(["?"] * len(repos))),
                  [name] + repos)
        builds = c.fetchall()
        if builds:
            most_recent_repo = builds[0][1]
        else:
            most_recent_repo = None
        if grade[0] is not None:
            c.execute('''SELECT COUNT(*) + 1 FROM grades, users WHERE assignment = ? AND score > ? AND grades.user = users.id AND users.super = 0''',
                      [name, grade[0]])
            rank, = c.fetchone()
        else:
            rank = None
        c.execute('''SELECT COUNT(*), AVG(score) FROM grades, users
                     WHERE assignment = ? AND score IS NOT NULL
                     AND grades.user = users.id AND users.super = 0''', [name])
        stats = c.fetchone()
        if stats[0] == 0:
            variance = None
            stddev = None
        else:
            c.execute("SELECT AVG((score - ?) * (score - ?)) FROM grades, users WHERE assignment = ? AND grades.user = users.id AND users.super = 0",
                      [stats[1], stats[1], name])
            variance, = c.fetchone()
            stddev = sqrt(variance)

        assignment_info = ((assignment.name, assignment.full_score, assignment.weight,
                            assignment.due_date, assignment.category, assignment.is_group,
                            assignment.manual_grading) + grade + (rank,) + stats + (stddev,))
        template_common = _template_common(c)
    return render_template("dashboard/assignments_one.html",
                           assignment_info=assignment_info,
                           builds=builds,
                           repos=repos,
                           most_recent_repo=most_recent_repo,
                           slipunits_now=slipunits_now,
                           can_build=can_build,
                           manual_grading=manual_grading,
                           hide_stats="-design" in assignment.name,
                           **template_common)


@blueprint.route("/dashboard/assignments/<name>/grades.json")
@require_csrf_token
@_require_login
def assignments_one_grades_json(name):
    with DbCursor() as c:
        data = Datasets.grade_distribution(c, name)
    if not data:
        abort(404)
    resp = Response(json.dumps(data))
    resp.headers["Content-Type"] = "application/json"
    return resp


@blueprint.route("/dashboard/builds/", defaults={"page": 1})
@blueprint.route("/dashboard/builds/page/<int:page>/")
@_require_login
def builds(page):
    page_size = 50
    page = max(1, page)
    with DbCursor() as c:
        student = _get_student(c)
        user_id, _, _, login, _, _ = student
        group_repos = get_groups(c, user_id)
        repos = [login] + group_repos
        c.execute('''SELECT build_name, source, status, score, `commit`, message, job, started
                     FROM builds WHERE source in (%s)
                     ORDER BY started DESC LIMIT ? OFFSET ?''' % (",".join(["?"] * len(repos))),
                  repos + [page_size + 1, (page - 1) * page_size])
        builds = c.fetchall()
        if not builds and page > 1:
            abort(404)
        more_pages = len(builds) == page_size + 1
        if more_pages:
            builds = builds[:-1]
        full_scores = {assignment.name: assignment.full_score
                       for assignment in config.assignments}
        builds_info = (build + (full_scores.get(build[6]),) for build in builds)
        template_common = _template_common(c)
    return render_template("dashboard/builds.html",
                           builds_info=builds_info,
                           page=page,
                           more_pages=more_pages,
                           **template_common)


@blueprint.route("/dashboard/builds/<name>/")
@_require_login
def builds_one(name):
    with DbCursor() as c:
        student = _get_student(c)
        user_id, _, _, login, _, _ = student
        group_repos = get_groups(c, user_id)
        repos = [login] + group_repos
        c.execute('''SELECT build_name, status, score, source, `commit`, message, job, started,
                     log FROM builds WHERE build_name = ? AND source in (%s)
                     LIMIT 1''' % (",".join(["?"] * len(repos))),
                  [name] + repos)
        build = c.fetchone()
        if not build:
            abort(404)
        build_info = build + (get_assignment_by_name(build[6]).full_score,)
        template_common = _template_common(c)
    return render_template("dashboard/builds_one.html",
                           build_info=build_info,
                           **template_common)

@blueprint.route("/dashboard/builds/<name>/stop", methods=["POST"])
@_require_login
def builds_one_stop(name):
    with DbCursor() as c:
        user_id, _, _, login, _, _ = _get_student(c)
        repos = [login] + get_groups(c, user_id)
        c.execute('''SELECT build_name, status, score, source, `commit`, message, job, started,
                     log FROM builds WHERE build_name = ? AND source in (%s)
                     LIMIT 1''' % (",".join(["?"] * len(repos))),
                  [name] + repos)
        if not c.fetchone():
            abort(404)
    for job in dockergrader_queue.snapshot():
        if job.build_name == name:
            dockergrader_queue._queue.remove(job)
    for worker in dockergrader_queue._workers:
        if worker.status == name:
            t, tid = worker.thread, -1
            if hasattr(t, '_thread_id'):
                tid = t._thread_id
            else:
                for id, thread in threading._active.items():
                    if thread is t:
                        tid = id
            ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_long(tid), ctypes.py_object(KeyboardInterrupt))
            # Python 3.7 updates first parameter type to unsigned long
            # This is QUITE the hack...
    with DbCursor() as c:
        c.execute('''UPDATE builds SET status = ?, updated = ?, log = ?
                        WHERE build_name = ?''',
                    [1, now_str(), "Build interrupted.", name])
        student = _get_student(c)
        user_id, _, _, login, _, _ = student
        group_repos = get_groups(c, user_id)
        repos = [login] + group_repos
        c.execute('''SELECT build_name, status, score, source, `commit`, message, job, started,
                     log FROM builds WHERE build_name = ? AND source in (%s)
                     LIMIT 1''' % (",".join(["?"] * len(repos))),
                  [name] + repos)
        build = c.fetchone()
        build_info = build + (get_assignment_by_name(build[6]).full_score,)
        template_common = _template_common(c)
    return render_template("dashboard/builds_one.html",
                           build_info=build_info,
                           **template_common)

@blueprint.route("/dashboard/build_now/", methods=["POST"])
@_require_login
def build_now():
    job_name = request.form.get("f_job_name")
    repo = request.form.get("f_repo")
    graded = False if "f_graded" in request.form and request.form.get("f_graded") == "False" else True
    assignment = get_assignment_by_name(job_name)
    if not assignment:
        abort(400)

    with DbCursor() as c:
        assignment = assignment.student_view(c, repo)
        if assignment.manual_grading:
            abort(400)
        student = _get_student(c)
        user_id, _, _, login, _, _ = student
        super_value = get_super(c, user_id)
        dropped = super_value is not None and super_value < 0
        if assignment.is_group:
            repos = get_groups(c, user_id)
        else:
            repos = [login]

        if repo not in repos:
            abort(403)

    if (graded and now_compare(assignment.not_visible_before, add_grace_period(assignment.cannot_build_after)) != 0) or dropped:
        abort(400)

    branch_hash = get_branch_hash(repo, "master") or get_branch_hash(repo, "main")
    message = None
    if branch_hash:
        message = get_commit_message(repo, branch_hash)

    build_type = "build"
    if not graded:
        build_type = "build-ungraded"

    # This section doesn't absolutely NEED to be consistent with the previous transaction,
    # since we have not specified any actual data constraints. The only possible logical error
    # would be to fulfill a request when the current user's permissions have been revoked
    # between these two transactions.
    with DbCursor() as c:
        build_name = create_build(c, job_name, repo, branch_hash, message, build_type)

    if should_limit_source(repo, job_name):
        rate_limit_fail_build(build_name)
    else:
        job = Job(build_name, repo, "Manual build.", graded)
        dockergrader_queue.enqueue(job)

    return redirect(url_for("dashboard.builds_one", name=build_name))


@blueprint.route("/dashboard/group/")
@_require_login
def group():
    if not config.groups_enabled:
        abort(404)
    with DbCursor() as c:
        student = _get_student(c)
        user_id, _, _, login, _, _ = student

        grouplimit = get_grouplimit(c, user_id)
        can_add_groups = grouplimit > 0

        # Fetch established groups
        c.execute('''SELECT users.name, users.email, users.github, users.login, groupsusers.`group`
                     FROM groupsusers LEFT JOIN users ON groupsusers.user = users.id
                     WHERE groupsusers.`group` IN
                        (SELECT `group` from groupsusers WHERE user = ?)
                     ORDER BY groupsusers.`group`, users.name ASC''', [user_id])
        partners = c.fetchall()
        groups = OrderedDict()
        for name, email, github, login, group in partners:
            groups.setdefault(group, []).append((name, email, github, login))

        # Fetch all my groups that are waiting on other people to accept
        c.execute('''SELECT users.name, invitations.status, invitations.invitation_id
                     FROM invitations LEFT JOIN users ON invitations.user = users.id
                     WHERE invitations.invitation_id IN
                         (SELECT invitation_id FROM invitations WHERE user = ? AND status = ?)
                     ORDER BY invitations.invitation_id, users.name''', [user_id, ACCEPTED])
        invitees = c.fetchall()
        proposed_groups = OrderedDict()
        for name, status, invitation_id in invitees:
            proposed_groups.setdefault(invitation_id, []).append((name, status))

        # Fetch all groups that want me
        c.execute('''SELECT users.name, invitations.status, invitations.invitation_id
                     FROM invitations LEFT JOIN users ON invitations.user = users.id
                     WHERE users.id != ? AND invitations.invitation_id IN
                         (SELECT invitation_id FROM invitations WHERE user = ? AND status = ?)
                     ORDER BY invitations.invitation_id, users.name''', [user_id, user_id, INVITED])
        invitations = c.fetchall()
        proposing_groups = OrderedDict()
        for name, status, invitation_id in invitations:
            proposing_groups.setdefault(invitation_id, []).append((name, status))

        template_common = _template_common(c)

    return render_template("dashboard/group.html",
                           groups=groups.items(),
                           proposed_groups=proposed_groups.items(),
                           proposing_groups=proposing_groups.items(),
                           can_add_groups=can_add_groups,
                           min_size=config.group_min_size,
                           max_size=config.group_max_size,
                           **template_common)


@blueprint.route("/dashboard/group/respond/", methods=["POST"])
@_require_login
def group_respond():
    if not config.groups_enabled:
        abort(404)
    try:
        github_job = None
        mailer_jobs = []
        with DbCursor() as c:
            invitation_id = request.form.get("f_group")
            response = request.form.get("f_response")
            if not invitation_id:
                fail_validation("Expected an invitation identifier (probably a programming error)")
            if response not in ("accept", "reject"):
                fail_validation("Expected a response (probably a programming error)")
            student = _get_student(c)
            user_id, _, _, _, _, _ = student

            super_value = get_super(c, user_id)
            dropped = super_value is not None and super_value < 0
            if dropped:
                fail_validation("You are not enrolled in the class; contact a TA if you believe this is a mistake")

            c.execute('''SELECT status FROM invitations WHERE invitation_id = ? AND user = ?''',
                      [invitation_id, user_id])
            statuses = c.fetchall()
            if len(statuses) != 1:
                fail_validation("Invitation has already been responded to")
            status = statuses[0][0]
            if response == "accept":
                if status != INVITED:
                    fail_validation("Invitation has already been responded to")
                grouplimit = get_grouplimit(c, user_id)
                if grouplimit < 1:
                    fail_validation("You have joined too many groups already")
                c.execute('''UPDATE invitations SET status = ?
                             WHERE invitation_id = ? AND user = ?''',
                          [ACCEPTED, invitation_id, user_id])
                modify_grouplimit(c, user_id, -1)
                group_name, group_members = finalize_group_if_ready(c, invitation_id)
                if group_name:
                    if not config.github_read_only_mode:
                        group_githubs = []
                        for _, _, _, github in group_members:
                            assert github, "GitHub handle is empty"
                            group_githubs.append(github)
                        github_job = repomanager_queue.create(c, "assign_repo",
                                                              (group_name, group_githubs))
                    if config.mailer_enabled:
                        for _, name, email, github in group_members:
                            email_payload = create_email("group_confirm", email,
                                                         "%s has been created" % group_name,
                                                         group_name=group_name,
                                                         name=name, group_members=group_members)
                            mailer_job = mailer_queue.create(c, "send", email_payload)
                            mailer_jobs.append(mailer_job)
            elif response == "reject":
                if status not in (ACCEPTED, INVITED):
                    fail_validation("Invitation has already been rejected")
                c.execute('''UPDATE invitations SET status = ?
                             WHERE invitation_id = ? AND user = ?''',
                          [REJECTED, invitation_id, user_id])
                if status == ACCEPTED:
                    # Give them back +1 to their group limit
                    modify_grouplimit(c, user_id, +1)
        if config.mailer_enabled:
            for mailer_job in mailer_jobs:
                mailer_queue.enqueue(mailer_job)
        if github_job and not config.github_read_only_mode:
            repomanager_queue.enqueue(github_job)
        return redirect(url_for("dashboard.group"))
    except ValidationError as e:
        return redirect_with_error(url_for("dashboard.group"), e)


@blueprint.route("/dashboard/group/create/", methods=["POST"])
@_require_login
def group_create():
    if not config.groups_enabled:
        abort(404)
    try:
        githubs = request.form.getlist("f_github")
        github_job = None
        mailer_jobs = []
        with DbCursor() as c:
            student = _get_student(c)
            inviter_user_id, inviter_name, _, _, inviter_github, _ = student

            super_value = get_super(c, inviter_user_id)
            dropped = super_value is not None and super_value < 0
            if dropped:
                fail_validation("You are not enrolled in the class; contact a TA if you believe this is a mistake")

            grouplimit = get_grouplimit(c, inviter_user_id)
            if grouplimit < 1:
                fail_validation("You are in too many groups already")
            invitees = []
            invitation_user_ids = set()
            for github in githubs:
                if not github:
                    continue
                invitee = get_user_by_github(c, github)
                if invitee is None:
                    fail_validation("GitHub username not found: %s" % github)
                invitee_id, _, _, _, _, _ = invitee
                if invitee_id == inviter_user_id:
                    continue
                if invitee_id in invitation_user_ids:
                    continue
                invitation_user_ids.add(invitee_id)
                invitees.append(invitee)
            if not config.group_min_size <= len(invitation_user_ids) + 1 <= config.group_max_size:
                if config.group_min_size == config.group_max_size:
                    fail_validation("You need exactly %d people in your group" % config.group_min_size)
                else:
                    fail_validation("You need between %d and %d people in your group" % (
                        config.group_min_size, config.group_max_size))
            if config.mailer_enabled:
                for _, invitee_name, _, _, _, invitee_email in invitees:
                    email_payload = create_email("group_invite", invitee_email,
                                                 "%s has invited you to a group" % inviter_name,
                                                 inviter_name=inviter_name,
                                                 inviter_github=inviter_github,
                                                 invitee_name=invitee_name,
                                                 invitees=invitees)
                    mailer_job = mailer_queue.create(c, "send", email_payload)
                    mailer_jobs.append(mailer_job)
            invitation_id = get_next_autoincrementing_value(c, "group_next_invitation_id")
            for invitation_user_id in invitation_user_ids:
                c.execute("INSERT INTO invitations (invitation_id, user, status) VALUES (?, ?, ?)",
                          [invitation_id, invitation_user_id, INVITED])
            c.execute("INSERT INTO invitations (invitation_id, user, status) VALUES (?, ?, ?)",
                      [invitation_id, inviter_user_id, ACCEPTED])
            modify_grouplimit(c, inviter_user_id, -1)
            group_name, group_members = finalize_group_if_ready(c, invitation_id)
            if group_name:
                if not config.github_read_only_mode:
                    group_githubs = []
                    for _, _, _, github in group_members:
                        assert github, "GitHub handle is empty"
                        group_githubs.append(github)
                    github_job = repomanager_queue.create(c, "assign_repo",
                                                          (group_name, group_githubs))
                if config.mailer_enabled:
                    for _, name, email, github in group_members:
                        email_payload = create_email("group_confirm", email,
                                                     "%s has been created" % group_name,
                                                     group_name=group_name,
                                                     name=name, group_members=group_members)
                        mailer_job = mailer_queue.create(c, "send", email_payload)
                        mailer_jobs.append(mailer_job)
        if config.mailer_enabled:
            for mailer_job in mailer_jobs:
                mailer_queue.enqueue(mailer_job)
        if github_job and not config.github_read_only_mode:
            repomanager_queue.enqueue(github_job)
        return redirect(url_for("dashboard.group"))
    except ValidationError as e:
        return redirect_with_error(url_for("dashboard.group"), e)
