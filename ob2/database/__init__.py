import apsw
import ob2.config as config
from ob2.config.assignment import Assignment
from ob2.database.virtual import GenericReadOnlyVTModule
from ob2.util.hooks import apply_filters


class DbCursor(object):
    """
    Creates a database handle with transaction semantics. Usage:

        with DbCursor() as c:
            c.execute("SELECT ... ")
            c.fetchall()

    A DbCursor cannot be used more than once, since we close and flush the connection once the first
    transaction completes. You should try to keep blocking operations (disk or network) out of the
    transaction.

    """
    def __init__(self, path=None, read_only=False):
        if path is None:
            path = config.database_path
        if read_only:
            flags = apsw.SQLITE_OPEN_READONLY
        else:
            flags = apsw.SQLITE_OPEN_CREATE | apsw.SQLITE_OPEN_READWRITE
        self.connection = apsw.Connection(path, flags)
        self.connection.setbusytimeout(5000)
        for module in apply_filters("database-vtmodules", [self.get_assignments_vtmodule()]):
            module.registerWithConnection(self.connection)

    def __enter__(self):
        self.connection.__enter__()
        return self.connection.cursor()

    def __exit__(self, *args):
        self.connection.__exit__(*args)
        # We need to explicitly call the destructor in order to make sure locks are freed.
        # Otherwise, Python is free to delay the destructor until a future point in time, which may
        # cause deadlock.
        del self.connection

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
