import sys
from ob2.database import DbCursor


def migrate():
    """
    See README.md for schema documentation.

    """
    with DbCursor() as c:
        schema_version = None

        # Determine the schema version
        c.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        tables = c.fetchall()
        if ("options",) in tables:
            c.execute("SELECT value FROM options WHERE key = 'schema_version'")
            schema_version, = c.fetchone()

        # Migration 1: Create options table
        if schema_version is None:
            assert sys.stdin.isatty(), ("Cowardly refusing to perform database migration if I'm "
                                        "not connected to an actual human.\n"
                                        "Please run the database migration interactively, and "
                                        "I'll never demand your attention again.")
            response = raw_input("Looks like the database db.sqlite3 hasn't been set up yet.\n" +
                                 "Set it up now? [Yn] ")
            if "yes"[:len(response)] != response.lower():
                sys.exit(0)
            print "Running initial migration"
            c.execute('''CREATE TABLE options (
                         key TEXT PRIMARY KEY, value TEXT)''')
            c.execute("INSERT INTO options (key, value) VALUES ('schema_version', '1')")
            schema_version = "1"

        # Migration 2: Create users table
        if schema_version == "1":
            print "Running migration 2: Create users table"
            c.execute('''CREATE TABLE users (
                         id INT PRIMARY KEY, name TEXT, sid TEXT, login TEXT, github TEXT,
                         email TEXT, super INT, grouplimit INT)''')
            c.execute("UPDATE options SET value = '2' WHERE key = 'schema_version'")
            schema_version = "2"

        # Migration 3: Create grades and gradeslog tables
        if schema_version == "2":
            print "Running migration 3: Create grades and gradeslog table"
            c.execute('''CREATE TABLE gradeslog (
                         transaction_name TEXT, description TEXT, source TEXT, updated TEXT,
                         user INT, assignment TEXT, score REAL, slipunits INT)''')
            c.execute('''CREATE TABLE grades (
                         user INT, assignment TEXT, score REAL, slipunits INT, updated TEXT,
                         manual INT, PRIMARY KEY(user, assignment))''')
            c.execute("UPDATE options SET value = '3' WHERE key = 'schema_version'")
            schema_version = "3"

        # Migration 4: Create builds table
        if schema_version == "3":
            print "Running migration 4: Create builds table"
            c.execute('''CREATE TABLE builds (
                         build_name TEXT, source TEXT, `commit` TEXT, message TEXT, job TEXT,
                         status INT, score REAL, started TEXT, updated TEXT, log TEXT)''')
            c.execute("UPDATE options SET value = '4' WHERE key = 'schema_version'")
            schema_version = "4"

        # Migration 5: Create repomanager table
        if schema_version == "4":
            print "Running migration 5: Create repomanager table"
            c.execute('''CREATE TABLE repomanager (id INT PRIMARY KEY, operation TEXT,
                         payload TEXT, updated TEXT, completed INT)''')
            c.execute("UPDATE options SET value = '5' WHERE key = 'schema_version'")
            schema_version = "5"

        # Migration 6: Create groupsusers table
        if schema_version == "5":
            print "Running migration 6: Create groupsusers table"
            c.execute('''CREATE TABLE groupsusers (user INT, `group` TEXT,
                                                   PRIMARY KEY(user, `group`))''')
            c.execute("UPDATE options SET value = '6' WHERE key = 'schema_version'")
            schema_version = "6"

        # Migration 7: Create invitations table
        if schema_version == "6":
            print "Running migration 7: Create invitations table"
            c.execute('''CREATE TABLE invitations (
                         invitation_id INT, user INT, status INT,
                         PRIMARY KEY(invitation_id, user))''')
            c.execute("UPDATE options SET value = '7' WHERE key = 'schema_version'")
            schema_version = "7"

        # Migration 8: Create mailerqueue table
        if schema_version == "7":
            print "Running migration 8: Create mailerqueue table"
            c.execute('''CREATE TABLE mailerqueue (id INT PRIMARY KEY, operation TEXT,
                         payload TEXT, updated TEXT, completed INT)''')
            c.execute("UPDATE options SET value = '8' WHERE key = 'schema_version'")
            schema_version = "8"

        # Migration 9: Add 'photo' field to users
        if schema_version == "8":
            print "Running migration 9: Add 'photo' field to users"
            c.execute("ALTER TABLE users ADD COLUMN photo BLOB;")
            c.execute("UPDATE options SET value = '9' WHERE key = 'schema_version'")
            schema_version = "9"
