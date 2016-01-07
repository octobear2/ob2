from collections import OrderedDict

import ob2.config as config
from ob2.database import DbCursor


_exports = {}
get_export_by_name = _exports.get


def register_export(fn):
    _exports[fn.__name__] = fn
    return fn


@register_export
def student_roster_with_grades():
    with DbCursor() as c:
        c.execute("SELECT id, name, sid, login, github, email, super FROM users")
        students = [list(student) + [None] * (2 * len(config.assignments))
                    for student in c.fetchall()]
        c.execute("SELECT user, assignment, score, slipunits FROM grades")
        grades = c.fetchall()
    if students:
        student_index = {student[0]: student for student in students}
        offset = len(students[0]) - 2 * len(config.assignments)
        assignment_index = {assignment.name: 2 * index + offset
                            for index, assignment in enumerate(config.assignments)}
        for user, assignment, score, slipunits in grades:
            index = assignment_index.get(assignment)
            if index is None:
                continue
            student_index[user][index] = score
            if slipunits is None:
                slipunits = 0
            student_index[user][index + 1] = slipunits
        dataset = students
        headers = ["Database ID", "Name", "SID", "Login", "GitHub Username", "Email", "Staff"]
        for assignment in config.assignments:
            headers += ["%s grade" % assignment.name,
                        "%s slip %s" % (assignment.name, config.slip_unit_name_plural)]
    return headers, dataset


@register_export
def repo_best_builds():
    with DbCursor() as c:
        c.execute('''SELECT build_name, source, `commit`, message, job, status, score
                     FROM builds ORDER BY started ASC''')
        builds = c.fetchall()

    best_score = OrderedDict()
    best_build = OrderedDict()
    for build_name, source, commit, message, job, status, score in builds:
        best_score.setdefault(job, {})
        if source not in best_score[job] or best_score[job][source] <= score:
            best_score[job][source] = score
            best_build.setdefault(job, {})[source] = (build_name, source, commit, message, job,
                                                      status, score)
    dataset = [build for job_builds in best_build.values() for build in job_builds.values()]
    headers = ["Build Name", "Source", "Commit", "Message", "Job", "Status", "Score"]
    return headers, dataset


if config.groups_enabled:
    @register_export
    def group_names_and_emails():
        with DbCursor() as c:
            c.execute("""SELECT groupsusers.`group`, GROUP_CONCAT(users.id, "|"),
                         GROUP_CONCAT(users.name, "|"), GROUP_CONCAT(users.sid, "|"),
                         GROUP_CONCAT(users.login, "|"), GROUP_CONCAT(users.github, "|"),
                         GROUP_CONCAT(users.email, "|")
                         FROM groupsusers LEFT JOIN users ON groupsusers.user = users.id
                         GROUP BY groupsusers.`group`""")
            dataset = c.fetchall()
        headers = ["Group Name", "Database ID", "Name", "SID", "Login", "GitHub Username", "Email"]
        return headers, dataset
