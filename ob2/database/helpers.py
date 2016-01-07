"""
Helper methods for database operations.

Each function takes a database cursor as its first parameter. The caller is responsible for
ensuring the proper transaction semantics are preserved and lock starvation is minimized.

"""

from collections import Counter

from ob2.util.time import now_str
from ob2.util.assignments import get_assignment_name_set
from ob2.util.build_constants import QUEUED
from ob2.util.config_data import get_repo_type
from ob2.util.group_constants import ACCEPTED


def get_next_autoincrementing_value(c, option_name):
    c.execute('''SELECT value FROM options WHERE key = ?''', [option_name])
    results = c.fetchall()
    if not results:
        next_value = 1
        c.execute('''INSERT INTO options (key, value) VALUES (?, ?)''', [option_name,
                                                                         str(next_value)])
    else:
        (current_value,), = results
        next_value = int(current_value) + 1
        c.execute('''UPDATE options SET value = ? WHERE key = ?''', [str(next_value),
                                                                     option_name])
    return next_value


def get_repo_owners(c, repo_name):
    """
    Given the name of a repository, return the list of users (user id's) that own the repository.
    An empty list may be returned if no users match.

    """
    repo_type = get_repo_type(repo_name)
    if repo_type == "group":
        c.execute('''SELECT users.id
                     FROM groupsusers LEFT JOIN users ON groupsusers.user = users.id
                     WHERE groupsusers.`group` = ?''', [repo_name])
        return [user_id for user_id, in c.fetchall()]
    elif repo_type == "personal":
        c.execute('''SELECT id FROM users WHERE login = ? LIMIT 1''', [repo_name])
        try:
            id, = c.fetchone()
            return [id]
        except TypeError:
            return []


def get_groups(c, user_id):
    c.execute('''SELECT `group` FROM groupsusers WHERE user = ?''', [user_id])
    return [group for group, in c.fetchall()]


def get_grouplimit(c, user_id):
    c.execute('''SELECT grouplimit FROM users WHERE id = ?''', [user_id])
    try:
        grouplimit, = c.fetchone()
        return grouplimit
    except TypeError:
        pass


def modify_grouplimit(c, user_id, modification=-1):
    c.execute("UPDATE users SET grouplimit = grouplimit + ? WHERE id = ?", [modification, user_id])


def finalize_group_if_ready(c, invitation_id):
    c.execute('''SELECT users.id, users.name, users.email, users.github, invitations.status
                 FROM invitations LEFT JOIN users ON invitations.user = users.id
                 WHERE invitations.invitation_id = ?''', [invitation_id])
    members = c.fetchall()
    for _, _, _, _, status in members:
        if status != ACCEPTED:
            return None, []
    for _, _, _, github, _ in members:
        if not github:
            raise RuntimeError("finalize_group_if_ready: Group finalized with unregistered student")
    c.execute("DELETE FROM invitations WHERE invitation_id = ?", [invitation_id])
    group_number = get_next_autoincrementing_value(c, "group_next_group_number")
    group_name = "group%d" % (group_number)
    for user, _, _, _, _ in members:
        c.execute("INSERT INTO groupsusers (user, `group`) VALUES (?, ?)", [user, group_name])
    group_members = [(user_id, name, email, github) for user_id, name, email, github, _ in members]
    return group_name, group_members


def get_user_by_id(c, user_id):
    c.execute('''SELECT id, name, sid, login, github, email FROM users
                 WHERE id = ?''', [user_id])
    return c.fetchone()


def get_users_by_ids(c, user_ids):
    c.execute('''SELECT id, name, sid, login, github, email FROM users
                 WHERE id IN (%s)''' % (",".join(["?"] * len(user_ids))), user_ids)
    return {row[0]: row for row in c.fetchall()}


def get_user_by_github(c, github):
    c.execute('''SELECT id, name, sid, login, github, email FROM users
                 WHERE github = ?''', [github])
    return c.fetchone()


def get_user_by_login(c, login):
    c.execute('''SELECT id, name, sid, login, github, email FROM users
                 WHERE login = ?''', [login])
    return c.fetchone()


def get_user_by_student_id(c, sid):
    c.execute('''SELECT id, name, sid, login, github, email FROM users
                 WHERE sid = ?''', [sid])
    return c.fetchone()


def get_users_by_identifier(c, identifier):
    """
    Looks up a list of users based on an identifier, for the enter-grades script. If the identifier
    is ambiguous (see get_valid_ambiguous_identifiers), then the behavior of this function is
    undefined.

    Always returns a list (but it may be empty).

    """
    for field in ("login", "sid", "name"):
        c.execute("SELECT id, name, sid, login, github, email FROM users WHERE %s = ?" % field,
                  [identifier])
        user = c.fetchone()
        if user:
            return [user]
    c.execute('''SELECT id, name, sid, login, github, email
                 FROM groupsusers LEFT JOIN users ON groupsusers.user = users.id
                 WHERE `group` = ?''', [identifier])
    return c.fetchall()


def get_valid_ambiguous_identifiers(c):
    c.execute("SELECT sid, login, name FROM users")
    identifiers_counter = Counter([identifier for user in c.fetchall()
                                   for identifier in user if identifier])
    c.execute("SELECT distinct `group` FROM groupsusers")
    identifiers_counter.update([group for group, in c.fetchall() if group])
    get_key = lambda(key, count): key
    get_count = lambda(key, count): count
    valid_identifiers = map(get_key, filter(lambda i: get_count(i) == 1,
                                            identifiers_counter.viewitems()))
    ambiguous_identifiers = map(get_key, filter(lambda i: get_count(i) > 1,
                                                identifiers_counter.viewitems()))
    return valid_identifiers, ambiguous_identifiers


def get_super(c, user_id):
    c.execute("SELECT super FROM users WHERE id = ?", [user_id])
    try:
        super_, = c.fetchone()
        return super_
    except TypeError:
        pass


def get_photo(c, user_id):
    c.execute("SELECT photo FROM users WHERE id = ?", [user_id])
    try:
        photo, = c.fetchone()
        return buffer(photo)
    except TypeError:
        pass


def create_build(c, job_name, source, commit, message):
    build_number = get_next_autoincrementing_value(c, "dockergrader_last_build_number")
    build_name = "%s-build-%d" % (job_name, build_number)
    c.execute('''INSERT INTO builds (build_name, source, `commit`, message, job, status, score,
                 started, updated, log) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              [build_name, source, commit, message, job_name, QUEUED, 0.0, now_str(),
               now_str(), None])
    return build_name


def assign_grade_batch(c, users, assignment, score, slipunits, transaction_name, description,
                       source, manual=False, dont_lower=False):
    """
    Assigns a new grade to one or more students. Also supports assigning slip units. You can use
    the special value `None` for score and/or slipunits to use the current value. If the dont_lower
    flag is True, then anybody in `users` who currently has a higher grade will be removed from
    the operation (and slip days will not be adjusted either).

    Returns a list of user ids whose grades were affected (will always be a subset of users).

    """
    if assignment not in get_assignment_name_set():
        raise ValueError("Assignment %s is not known" % assignment)
    if not users:
        return []
    if score is None and slipunits is None:
        return []
    timestamp = now_str()

    if dont_lower:
        if score is None:
            # It makes no sense to do this.
            raise ValueError("You can not use both dont_lower=True and have a score of None, if " +
                             "slipunits is not None.")

        # This comparison (old score vs new score) MUST be done in Sqlite in order for the result
        # to be correct. Sqlite will round the floating point number in the same way it did when
        # the original result was inserted, and the two values will be equal. Converting this to a
        # float in another language may produce undesirable effects.
        c.execute('''SELECT user FROM grades
                     WHERE assignment = ? AND score >= ? AND user IN (%s)''' %
                  (','.join(['?'] * len(users))), [assignment, score] + users)
        users = list(set(users) - {user for user, in c.fetchall()})
        if not users:
            return []

    c.execute('''SELECT users.id FROM grades LEFT JOIN users
                 ON grades.user = users.id WHERE grades.assignment = ? AND users.id IN (%s)''' %
              (','.join(["?"] * len(users))), [assignment] + users)
    for user in list(set(users) - {user for user, in c.fetchall()}):
        # Insert dummy values first, and we will update them later
        c.execute('''INSERT INTO grades (user, assignment) VALUES (?, ?)''',
                  [user, assignment])

    c.execute('''UPDATE grades SET updated = ?, manual = ?
                 WHERE assignment = ? AND user IN (%s)''' % (','.join(['?'] * len(users))),
              [timestamp, int(manual), assignment] + users)

    if score is not None:
        c.execute('''UPDATE grades SET score = ?
                     WHERE assignment = ? AND user IN (%s)''' % (','.join(['?'] * len(users))),
                  [score, assignment] + users)

    if slipunits is not None:
        c.execute('''UPDATE grades SET slipunits = ?
                     WHERE assignment = ? AND user IN (%s)''' % (','.join(['?'] * len(users))),
                  [slipunits, assignment] + users)

    c.execute('''INSERT INTO gradeslog (transaction_name, description, source, updated, user,
                                        assignment, score, slipunits)
                 VALUES %s''' % (','.join(['(?,?,?,?,?,?,?,?)'] * len(users))),
              [field for entry in [[transaction_name, description, source, timestamp, user,
                                    assignment, score, slipunits]
                                   for user in users] for field in entry])
    return users
