import apsw
import ob2.config as config
import threading
from ob2.config.assignment import Assignment
from ob2.database.virtual import GenericReadOnlyVTModule
from ob2.util.hooks import apply_filters

# For low-traffic applications, a global Python-level lock is the recommended
# way to prevent database lock conflicts.
global_database_lock = threading.Lock()


class DbCursor(object):
    """
    Creates a database handle with transaction semantics. Usage:

        with DbCursor() as c:
            c.execute("...")
            c.fetchall()

    A DbCursor cannot be used more than once, since we close and flush the connection once the first
    transaction completes. You should try to keep blocking operations (disk or network) out of the
    transaction.

    For daemon threads, you should catch apsw.Error and retry the transaction when it fails. Make
    sure that your retries are idempotent.

    """
    def __init__(self, path=None, read_only=False):
        if path is None:
            path = config.database_path
        if read_only:
            flags = apsw.SQLITE_OPEN_READONLY
        else:
            flags = apsw.SQLITE_OPEN_CREATE | apsw.SQLITE_OPEN_READWRITE

        # The global lock is acquired in the constructor, so you must never instantiate a DbCursor
        # object without actually using it.
        global_database_lock.acquire()

        try:
            # The connection setup must be done in the constructor, NOT in __enter__.
            # If __enter__ raises an exception, then the __exit__ method will also be called.
            self.connection = apsw.Connection(path, flags)
            self.connection.setbusytimeout(5000)
            for module in apply_filters("database-vtmodules", [self.get_assignments_vtmodule()]):
                module.registerWithConnection(self.connection)
        except Exception:
            global_database_lock.release()
            raise

    def __enter__(self):
        self.connection.__enter__()

        # We must save the cursor as a state variable, so we hold the only reference to it and we
        # can safely call the destructor for the cursor in __exit__.
        self.cursor = self.connection.cursor()
        return self

    def __exit__(self, *args):
        try:
            self.connection.__exit__(*args)

            # We need to explicitly call the destructor in order to make sure locks are freed.
            # Otherwise, Python is free to delay the destructor until a future point in time, which may
            # cause deadlock.
            del self.cursor
            del self.connection
        finally:
            global_database_lock.release()

    def execute(self, *args):
        return self.cursor.execute(*args)

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()

    def getdescription(self):
        return self.cursor.getdescription()

    _assignments_vtmodule = None

    @classmethod
    def get_assignments_vtmodule(cls):
        """
        Builds the virtual table module for the 'assignments' virtual table. The module object is
        cached for performance.

        This function is synchronized via the GIL. (But that shouldn't matter anyway, because there
        are plenty of database operations at initialization time, which runs in serial. So, the
        cache will always be primed before the threading begins.)

        """
        if not cls._assignments_vtmodule:
            keys, types = [], []
            for key, type_ in Assignment.schema:
                keys.append(key)
                types.append(type_)
            values = [assignment.get_fields() for assignment in config.assignments]
            cls._assignments_vtmodule = GenericReadOnlyVTModule("assignments", keys, types, values)

        return cls._assignments_vtmodule
