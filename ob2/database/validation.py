"""
Validation that can be run at initilization time to ensure logical constraints of the database.

"""

from os.path import exists

import ob2.config as config
from ob2.database import DbCursor
from ob2.util.assignments import get_assignment_name_set
from ob2.util.inst_account import get_inst_account_form_path


def validate_database_constraints():
    with DbCursor() as c:
        _validate_accounts(c)
        _validate_account_forms(c)
        _validate_grades(c)


def _validate_accounts(c):
    c.execute("SELECT id, name, sid, login, github, email FROM users")
    for user_id, name, sid, login, github, email in c.fetchall():
        assert type(user_id) is int
        assert user_id > 0
        assert name
        assert sid
        assert login
        assert email


def _validate_account_forms(c):
    if config.inst_account_enabled:
        c.execute("SELECT login FROM users WHERE login IS NOT NULL")
        logins = [login for login, in c.fetchall()]
        for login in logins:
            expected_path = get_inst_account_form_path(login)
            assert exists(expected_path), ("Cannot find account form for %s at %s" %
                                           (config.course_login_format % login, expected_path))


def _validate_grades(c):
    assignment_names = get_assignment_name_set()
    c.execute("SELECT DISTINCT assignment FROM grades")
    for assignment_name, in c.fetchall():
        assert assignment_name in assignment_names, ("Unknown assignment in database: %s" %
                                                     assignment_name)
    c.execute("SELECT DISTINCT assignment FROM gradeslog")
    for assignment_name, in c.fetchall():
        assert assignment_name in assignment_names, ("Unknown assignment in database: %s" %
                                                     assignment_name)
    c.execute("SELECT DISTINCT job FROM builds")
    for assignment_name, in c.fetchall():
        assert assignment_name in assignment_names, ("Unknown assignment in database: %s" %
                                                     assignment_name)
