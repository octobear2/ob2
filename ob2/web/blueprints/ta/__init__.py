import apsw
import binascii
import csv
import json
import StringIO
import traceback
from collections import OrderedDict
from flask import (Blueprint, Response, abort, flash, redirect, render_template, request, session,
                   url_for)
from functools import wraps
from math import sqrt

import ob2.config as config
from ob2.config import (
    slip_unit_name_plural,
    student_photos_enabled,
)
from ob2.database import DbCursor
from ob2.database.export import get_export_by_name
from ob2.database.helpers import (
    assign_grade_batch,
    get_grouplimit,
    get_next_autoincrementing_value,
    get_photo,
    get_repo_owners,
    get_super,
    get_user_by_github,
    get_user_by_id,
    get_user_by_login,
    get_user_by_student_id,
    get_users_by_identifier,
    get_valid_ambiguous_identifiers,
    modify_grouplimit,
)
from ob2.dockergrader import dockergrader_queue
from ob2.util.authentication import authenticate_as_user
from ob2.util.config_data import get_assignment_by_name
from ob2.util.datasets import Datasets
from ob2.util.github_login import github_username, is_ta
from ob2.util.security import require_csrf_token
from ob2.util.validation import (float_or_none, int_or_none, same_length, fail_validation,
                                 ValidationError, redirect_with_error)

blueprint = Blueprint("ta", __name__, template_folder="templates")


def _template_common():
    return {"github_username": github_username(),
            "groups_enabled": config.groups_enabled}


def _require_ta(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not is_ta():
            if request.method == "GET":
                session["login_next__ta"] = request.base_url
            elif "login_next__ta" in session:
                del session["login_next__ta"]
            return redirect(url_for("onboarding.log_in"))
        else:
            if "login_next__ta" in session:
                del session["login_next__ta"]
            return fn(*args, **kwargs)

    return wrapped


@blueprint.route("/ta/")
@_require_ta
def index():
    return redirect(url_for("ta.assignments"))


@blueprint.route("/ta/enter_grades/")
@_require_ta
def enter_grades():
    assignment_names = [assignment.name for assignment in config.assignments]
    return render_template("ta/enter_grades.html",
                           assignment_names=assignment_names,
                           **_template_common())


@blueprint.route("/ta/enter_grades/validation_data/")
@require_csrf_token
@_require_ta
def enter_grades_validation_data():
    assignment_names = [assignment.name for assignment in config.assignments]
    min_scores = {assignment.name: assignment.min_score for assignment in config.assignments}
    max_scores = {assignment.name: assignment.max_score for assignment in config.assignments}
    with DbCursor() as c:
        valid_identifiers, ambiguous_identifiers = get_valid_ambiguous_identifiers(c)
    payload = {
        "assignment_names": assignment_names,
        "min_scores": min_scores,
        "max_scores": max_scores,
        "valid_identifiers": list(valid_identifiers),
        "ambiguous_identifiers": list(ambiguous_identifiers),
    }
    resp = Response("var enter_grades_validation_data = %s;" % json.dumps(payload))
    resp.headers["Content-Type"] = "text/javascript"
    return resp


@blueprint.route("/ta/enter_grades/confirm/", methods=["POST"])
@_require_ta
def enter_grades_confirm():
    try:
        f_step = request.form.get("f_step")
        if f_step not in ("1", "2"):
            fail_validation("Enum out of range (probably a programming error)")
        step = int(f_step)
        assignment_name = request.form.get("f_assignment")
        if not assignment_name:
            fail_validation("Assignment name is required")
        assignment = get_assignment_by_name(assignment_name)
        if assignment is None:
            fail_validation("Assignment not found: %s" % assignment_name)
        min_score, max_score = assignment.min_score, assignment.max_score

        description = request.form.get("f_description")
        if not description:
            fail_validation("Transaction description is required")

        transaction_source = github_username()

        entries = []
        user_id_set = set()

        with DbCursor() as c:
            valid_identifiers, ambiguous_identifiers = get_valid_ambiguous_identifiers(c)

            def try_add(f_student, f_score, f_slipunits):
                if not any((f_student, f_score, f_slipunits)):
                    return
                elif not f_student and (f_score or f_slipunits):
                    fail_validation("Expected student SID, login, or name, but none provided")
                elif f_student in ambiguous_identifiers:
                    fail_validation("The identifier '%s' is ambiguous. Please use another." %
                                    f_student)
                else:
                    if step == 1:
                        students = get_users_by_identifier(c, f_student)
                    elif step == 2:
                        student = get_user_by_id(c, f_student)
                        # Let the usual error handling take care of this case
                        students = [student] if student else []
                    if not students:
                        fail_validation("Student or group not found: %s" % f_student)
                    for student in students:
                        user_id, student_name, _, _, _, _ = student
                        if user_id in user_id_set:
                            fail_validation("Student was listed more than once: %s" % student_name)
                        try:
                            score = float_or_none(f_score)
                        except ValueError:
                            fail_validation("Not a valid score: %s" % f_score)
                        try:
                            slipunits = int_or_none(f_slipunits)
                        except ValueError:
                            fail_validation("Slip %s amount not valid: %s" % (slip_unit_name_plural,
                                                                              f_slipunits))
                        if slipunits is not None and slipunits < 0:
                            fail_validation("Slip %s cannot be negative" % slip_unit_name_plural)
                        if score is not None and not min_score <= score <= max_score:
                            fail_validation("Score is out of allowed range: %s (Range: %s to %s)" %
                                            (f_score, str(min_score), str(max_score)))
                        entries.append([user_id, score, slipunits])
                        user_id_set.add(user_id)

            if step == 1:
                f_students = request.form.getlist("f_student")
                f_scores = request.form.getlist("f_score")
                f_slipunitss = request.form.getlist("f_slipunits")
                if not same_length(f_students, f_scores, f_slipunitss):
                    fail_validation("Different numbers of students, scores, and slip %s " +
                                    "reported. Browser bug?" % slip_unit_name_plural)
                for f_student, f_score, f_slipunits in zip(f_students, f_scores, f_slipunitss):
                    try_add(f_student, f_score, f_slipunits)

            f_csv = request.form.get("f_csv", "")
            for row in csv.reader(StringIO.StringIO(f_csv), delimiter=",", quotechar='"'):
                if len(row) != 3:
                    fail_validation("CSV rows must contain 3 entries")
                try_add(*row)

            if not entries:
                fail_validation("No grade or slip %s changes entered" % slip_unit_name_plural)

            if step == 1:
                c.execute('''SELECT id, name, sid, login, github FROM users
                             WHERE id IN (%s)''' % (",".join(["?"] * len(entries))),
                          [user_id for user_id, _, _ in entries])
                students = c.fetchall()
                details_user = {}
                for user_id, name, sid, login, github in students:
                    details_user[user_id] = [name, sid, login, github]
                c.execute('''SELECT user, score, slipunits, updated FROM grades
                             WHERE assignment = ? AND user IN (%s)''' %
                          (",".join(["?"] * len(entries))),
                          [assignment.name] + [user_id for user_id, _, _ in entries])
                grades = c.fetchall()
                details_grade = {}
                for user_id, score, slipunits, updated in grades:
                    details_grade[user_id] = [score, slipunits, updated]
                entries_details = []
                for entry in entries:
                    user_id = entry[0]
                    entry_details = (entry + details_user.get(user_id, [None] * 4)
                                           + details_grade.get(user_id, [None] * 3))
                    entries_details.append(entry_details)
            elif step == 2:
                transaction_number = get_next_autoincrementing_value(
                    c, "enter_grades_last_transaction_number")
                transaction_name = "enter-grades-%s" % transaction_number
                for user_id, score, slipunits in entries:
                    assign_grade_batch(c, [user_id], assignment.name, score, slipunits,
                                       transaction_name, description, transaction_source,
                                       manual=True, dont_lower=False)
        if step == 1:
            entries_csv = StringIO.StringIO()
            entries_csv_writer = csv.writer(entries_csv, delimiter=",", quotechar='"')
            for entry in entries:
                entries_csv_writer.writerow(entry)
            return render_template("ta/enter_grades_confirm.html",
                                   entries_details=entries_details,
                                   entries_csv=entries_csv.getvalue(),
                                   assignment_name=assignment.name,
                                   description=description,
                                   full_score=assignment.full_score,
                                   **_template_common())
        elif step == 2:
            if len(entries) == 1:
                flash("1 grade committed", "success")
            else:
                flash("%d grades committed" % len(entries), "success")
            return redirect(url_for("ta.enter_grades"))
    except ValidationError as e:
        return redirect_with_error(url_for("ta.enter_grades"), e)


@blueprint.route("/ta/students/")
@_require_ta
def students():
    with DbCursor() as c:
        c.execute('''SELECT id, name, sid, login, github, email, super
                     FROM users ORDER BY super DESC, login''')
        students = c.fetchall()
    return render_template("ta/students.html",
                           students=students,
                           **_template_common())


@blueprint.route("/ta/students/<identifier>/", defaults={"type_": "github"})
@blueprint.route("/ta/students/github/<identifier>/", defaults={"type_": "_github_explicit"})
@blueprint.route("/ta/students/login/<identifier>/", defaults={"type_": "login"})
@blueprint.route("/ta/students/id/<int:identifier>/", defaults={"type_": "id"})
@blueprint.route("/ta/students/user_id/<int:identifier>/", defaults={"type_": "user_id"})
@blueprint.route("/ta/students/sid/<int:identifier>/", defaults={"type_": "sid"})
@blueprint.route("/ta/students/student_id/<int:identifier>/", defaults={"type_": "student_id"})
@_require_ta
def students_one(identifier, type_):
    with DbCursor() as c:
        student = None
        if type_ in ("id", "user_id"):
            student = get_user_by_id(c, identifier)
        elif type_ in ("github", "_github_explicit"):
            student = get_user_by_github(c, identifier)
        elif type_ == "login":
            student = get_user_by_login(c, identifier)
        elif type_ in ("sid", "student_id"):
            student = get_user_by_student_id(c, identifier)
        if student is None:
            abort(404)
        user_id, _, _, _, _, _ = student
        super_ = get_super(c, user_id)
        photo = None
        if student_photos_enabled:
            photo = get_photo(c, user_id)
        c.execute('''SELECT users.id, users.name, users.github, groupsusers.`group`
                     FROM groupsusers LEFT JOIN users ON groupsusers.user = users.id
                     WHERE groupsusers.`group` IN
                         (SELECT `group` FROM groupsusers WHERE user = ?)''', [user_id])
        groups = OrderedDict()
        for g_user_id, g_name, g_github, g_group in c.fetchall():
            groups.setdefault(g_group, []).append((g_user_id, g_name, g_github))
        grouplimit = get_grouplimit(c, user_id)
        c.execute('''SELECT transaction_name, source, assignment, score, slipunits, updated,
                     description FROM gradeslog WHERE user = ? ORDER BY updated DESC''',
                  [user_id])
        entries = c.fetchall()
        full_scores = {assignment.name: assignment.full_score
                       for assignment in config.assignments}
        events = [entry + (full_scores.get(entry[2]),) for entry in entries]
        c.execute("SELECT assignment, score, slipunits, updated FROM grades WHERE user = ?",
                  [user_id])
        grade_info = {assignment: (score, slipunits, updated)
                      for assignment, score, slipunits, updated in c.fetchall()}
        assignments_info = [(a.name, a.full_score, a.weight, a.due_date) +
                            grade_info.get(a.name, (None, None, None))
                            for a in config.assignments]
    return render_template("ta/students_one.html",
                           student=student,
                           super_=super_,
                           photo=photo,
                           groups=groups.items(),
                           grouplimit=grouplimit,
                           events=events,
                           assignments_info=assignments_info,
                           **_template_common())


@blueprint.route("/ta/login_as/", methods=["POST"])
@_require_ta
def login_as():
    user_id = request.form.get("f_user_id")
    if not user_id:
        abort(400)
    authenticate_as_user(user_id)
    return redirect(url_for("dashboard.index"))


@blueprint.route("/ta/modify_grouplimit_now/", methods=["POST"])
@_require_ta
def modify_grouplimit_now():
    user_id = request.form.get("f_user_id")
    action = request.form.get("f_action")
    if not user_id:
        abort(400)
    if action not in ("add", "subtract"):
        abort(400)
    with DbCursor() as c:
        student = get_user_by_id(c, user_id)
        if not student:
            abort(400)
        _, _, _, _, github, _ = student
        modification = {"add": +1,
                        "subtract": -1}
        modify_grouplimit(c, user_id, modification[action])
        grouplimit = get_grouplimit(c, user_id)
        flash("grouplimit has been set to %d" % grouplimit, "success")
    if github:
        return redirect(url_for("ta.students_one", identifier=github, type_="github"))
    else:
        return redirect(url_for("ta.students_one", identifier=user_id, type_="user_id"))


@blueprint.route("/ta/builds/", defaults={"page": 1})
@blueprint.route("/ta/builds/page/<int:page>/")
@_require_ta
def builds(page):
    page_size = 50
    page = max(1, page)
    with DbCursor() as c:
        c.execute('''SELECT build_name, source, status, score, `commit`, message, job, started
                     FROM builds ORDER BY started DESC LIMIT ? OFFSET ?''',
                  [page_size + 1, (page - 1) * page_size])
        builds = c.fetchall()
        if not builds and page > 1:
            abort(404)
        more_pages = len(builds) == page_size + 1
        if more_pages:
            builds = builds[:-1]
        full_scores = {assignment.name: assignment.full_score
                       for assignment in config.assignments}
        builds_info = (build + (full_scores.get(build[6]),) for build in builds)
    return render_template("ta/builds.html",
                           builds_info=builds_info,
                           page=page,
                           more_pages=more_pages,
                           **_template_common())


@blueprint.route("/ta/builds/<name>/")
@_require_ta
def builds_one(name):
    with DbCursor() as c:
        c.execute('''SELECT build_name, status, score, source, `commit`, message, job, started,
                     log FROM builds WHERE build_name = ? LIMIT 1''', [name])
        build = c.fetchone()
        if not build:
            abort(404)
        build_info = build + (get_assignment_by_name(build[6]).full_score,)
    return render_template("ta/builds_one.html",
                           build_info=build_info,
                           **_template_common())


@blueprint.route("/ta/assignments/")
@_require_ta
def assignments():
    with DbCursor() as c:
        c.execute('''SELECT assignment, count(*) FROM grades WHERE score IS NOT NULL
                     GROUP BY assignment''')
        counts_by_assignment = dict(c.fetchall())
    if counts_by_assignment:
        total_participants = max(counts_by_assignment.values())
    else:
        total_participants = 1
    assignments_info = [(a.name, a.full_score, a.weight, a.manual_grading,
                         a.not_visible_before, a.start_auto_building,
                         a.end_auto_building, a.due_date, a.cannot_build_after,
                         float(counts_by_assignment.get(a.name, 0)) / total_participants)
                        for a in config.assignments]
    return render_template("ta/assignments.html",
                           assignments_info=assignments_info,
                           **_template_common())


@blueprint.route("/ta/assignments/<name>/", defaults={"page": 1})
@blueprint.route("/ta/assignments/<name>/page/<int:page>/")
@_require_ta
def assignments_one(name, page):
    page_size = 50
    assignment = get_assignment_by_name(name)

    if not assignment:
        abort(404)

    with DbCursor() as c:
        c.execute('''SELECT id, name, sid, github, email, super, score, slipunits, updated
                     FROM grades LEFT JOIN users ON grades.user = users.id
                     WHERE assignment = ? ORDER BY super DESC, login''', [name])
        grades = c.fetchall()
        c.execute('''SELECT build_name, source, status, score, `commit`, message, started
                     FROM builds WHERE job = ? ORDER BY started DESC LIMIT ? OFFSET ?''',
                  [name, page_size + 1, (page - 1) * page_size])
        builds = c.fetchall()
        if not builds and page > 1:
            abort(404)
        more_pages = len(builds) == page_size + 1
        if more_pages:
            builds = builds[:-1]
        c.execute('''SELECT COUNT(*), AVG(score) FROM grades
                     WHERE assignment = ? AND score IS NOT NULL''', [name])
        stats = c.fetchone()
        if stats[0] == 0:
            variance = None
            stddev = None
        else:
            c.execute("SELECT AVG((score - ?) * (score - ?)) FROM grades WHERE assignment = ?",
                      [stats[1], stats[1], name])
            variance, = c.fetchone()
            stddev = sqrt(variance)

    assignment_info = ((assignment.name, assignment.full_score, assignment.min_score,
                        assignment.max_score, assignment.weight, assignment.due_date,
                        assignment.category, assignment.is_group, assignment.manual_grading,
                        assignment.not_visible_before, assignment.cannot_build_after,
                        assignment.start_auto_building, assignment.end_auto_building) +
                       stats + (stddev,))
    return render_template("ta/assignments_one.html",
                           grades=grades,
                           builds=builds,
                           assignment_info=assignment_info,
                           page=page,
                           more_pages=more_pages,
                           **_template_common())


@blueprint.route("/ta/assignments/<name>/grade_distribution.json")
@require_csrf_token
@_require_ta
def assignments_one_grade_distribution(name):
    with DbCursor() as c:
        data = Datasets.grade_distribution(c, name)
    if not data:
        abort(404)
    resp = Response(json.dumps(data))
    resp.headers["Content-Type"] = "application/json"
    return resp


@blueprint.route("/ta/assignments/<name>/timeseries_grade_percentiles.json")
@require_csrf_token
@_require_ta
def assignments_one_timeseries_grade_percentiles(name):
    with DbCursor() as c:
        data = Datasets.timeseries_grade_percentiles(c, name)
    if not data:
        abort(404)
    resp = Response(json.dumps(data))
    resp.headers["Content-Type"] = "application/json"
    return resp


@blueprint.route("/ta/repo/<repo>/")
@_require_ta
def repo(repo):
    with DbCursor() as c:
        owners = get_repo_owners(c, repo)
        if not owners:
            abort(404)
        c.execute('''SELECT id, name, sid, login, github, email, super, photo FROM users
                     WHERE id in (%s)''' % ",".join(["?"] * len(owners)), owners)
        students = c.fetchall()
        c.execute('''SELECT build_name, source, status, score, `commit`, message, job, started
                     FROM builds WHERE source = ? ORDER BY started DESC''', [repo])
        builds = c.fetchall()
        full_scores = {assignment.name: assignment.full_score
                       for assignment in config.assignments}
        builds_info = (build + (full_scores.get(build[6]),) for build in builds)

    return render_template("ta/repo.html",
                           repo=repo,
                           students=students,
                           builds_info=builds_info,
                           **_template_common())


@blueprint.route("/ta/gradeslog/", defaults={"page": 1})
@blueprint.route("/ta/gradeslog/page/<int:page>/")
@_require_ta
def gradeslog(page):
    page_size = 50
    page = max(1, page)
    with DbCursor() as c:
        c.execute('''SELECT gradeslog.transaction_name, gradeslog.source, users.id, users.name,
                     users.github, users.super, gradeslog.assignment, gradeslog.score,
                     gradeslog.slipunits, gradeslog.updated, gradeslog.description
                     FROM gradeslog LEFT JOIN users ON gradeslog.user = users.id
                     ORDER BY updated DESC LIMIT ? OFFSET ?''',
                  [page_size + 1, (page - 1) * page_size])
        entries = c.fetchall()
        if not entries and page > 1:
            abort(404)
        more_pages = len(entries) == page_size + 1
        if more_pages:
            entries = entries[:-1]
    full_scores = {assignment.name: assignment.full_score for assignment in config.assignments}
    events = [entry + (full_scores.get(entry[6]),) for entry in entries]
    return render_template("ta/gradeslog.html",
                           events=events,
                           page=page,
                           more_pages=more_pages,
                           **_template_common())


@blueprint.route("/ta/gradeslog/<name>/")
@_require_ta
def gradeslog_one(name):
    with DbCursor() as c:
        c.execute('''SELECT gradeslog.transaction_name, gradeslog.source, users.id, users.name,
                     users.github, users.super, gradeslog.assignment, gradeslog.score,
                     gradeslog.slipunits, gradeslog.updated, gradeslog.description
                     FROM gradeslog LEFT JOIN users ON gradeslog.user = users.id
                     WHERE gradeslog.transaction_name = ? LIMIT 1''', [name])
        entry = c.fetchone()
    assignment = get_assignment_by_name(entry[6])
    full_score = assignment.full_score if assignment else 0.0
    return render_template("ta/gradeslog_one.html",
                           entry=entry,
                           full_score=full_score,
                           **_template_common())


@blueprint.route("/ta/sql/", methods=["GET", "POST"])
@_require_ta
def sql():
    query = ""
    query_headers = query_rows = query_error = None
    query_more = False

    if request.method == "POST":
        action = request.form.get("f_action")
        query = request.form.get("f_query")

        try:
            if query:
                with DbCursor(read_only=True) as c:
                    c.execute(query)
                    query_rows = []

                    def stringify(d):
                        if isinstance(d, unicode):
                            return d.encode("utf-8")
                        # We want to display "0" here, because this is meant to be a direct
                        # connection to the database.
                        elif d is None:
                            return ""
                        else:
                            return str(d)

                    # We are not allowed to modify the query itself, so we're forced to truncate
                    # long lists of results with Python.
                    for _ in range(1000):
                        row = c.fetchone()
                        if not row:
                            break
                        else:
                            query_headers = c.getdescription()
                        query_rows.append(map(stringify, row))
                    if c.fetchone():
                        query_more = True
                    if not query_rows:
                        query_error = "No results"
        except apsw.Error:
            query_error = traceback.format_exc()

        if action == "export" and query_headers:
            result_string = StringIO.StringIO()
            result_writer = csv.writer(result_string, delimiter=",", quotechar='"')
            result_writer.writerow([header_name for header_name, header_type in query_headers])
            if query_rows:
                result_writer.writerows(query_rows)
            resp = Response(result_string.getvalue())
            resp.headers["Content-Type"] = "text/csv"
            resp.headers["Content-Disposition"] = "attachment; filename=query_results.csv"
            return resp

    return render_template("ta/sql.html",
                           query=query,
                           query_headers=query_headers,
                           query_rows=query_rows,
                           query_error=query_error,
                           query_more=query_more,
                           **_template_common())


@blueprint.route("/ta/queue_status/")
@_require_ta
def queue_status():
    queue_workers = dockergrader_queue.probe_workers()
    queue_jobs = dockergrader_queue.snapshot()
    return render_template("ta/queue_status.html",
                           queue_workers=queue_workers,
                           queue_jobs=queue_jobs,
                           **_template_common())


@blueprint.route("/ta/queue_status/worker/<int:identifier>/")
@_require_ta
def queue_status_worker(identifier):
    worker_info = dockergrader_queue.probe_worker(identifier, with_log=True)
    if not worker_info:
        abort(400)
    return render_template("ta/queue_status_worker.html",
                           worker_info=worker_info,
                           **_template_common())


@blueprint.route("/ta/export/")
@_require_ta
def export():
    return render_template("ta/export.html", **_template_common())


@blueprint.route("/ta/export/<name>/")
@_require_ta
def export_one(name):
    export_driver = get_export_by_name(name)
    if not export_driver:
        abort(404)
    headers, dataset = export_driver()

    def stringify(d):
        if isinstance(d, unicode):
            return d.encode("utf-8")
        # We do NOT Want To Display "0" Here, Because It Just Adds Confusion To Spreadsheets.
        elif not d:
            return ""
        else:
            return str(d)

    dataset = map(lambda data: map(stringify, data), dataset)
    result_string = StringIO.StringIO()
    result_writer = csv.writer(result_string, delimiter=",", quotechar='"')
    if headers:
        result_writer.writerow(headers)
    if dataset:
        result_writer.writerows(dataset)
    resp = Response(result_string.getvalue())
    resp.headers["Content-Type"] = "text/csv"
    resp.headers["Content-Disposition"] = "attachment; filename=%s.csv" % name
    return resp
