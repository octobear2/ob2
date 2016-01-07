import apsw

_PY_TO_SQLITE = {str: "TEXT",
                 int: "INT",
                 float: "REAL"}


class GenericReadOnlyVTModule(object):
    def __init__(self, name, keys, types, values):
        self.name = name
        self.keys = keys
        self.types = types
        self.values = values
        self._module_name = "%sVT" % name

    def Create(self, *args):
        table = GenericReadOnlyVTTable(self)
        ddl = ", ".join(["`%s` %s" % (key, _PY_TO_SQLITE[type_])
                         for key, type_ in zip(self.keys, self.types)])
        return "CREATE TABLE %s (%s)" % (self.name, ddl), table

    def registerWithConnection(self, connection):
        connection.createmodule(self._module_name, self)
        connection.cursor().execute("CREATE VIRTUAL TABLE IF NOT EXISTS %s USING %s()" %
                                    (self.name, self._module_name))

    Connect = Create


class GenericReadOnlyVTTable(object):
    BestIndex = Destroy = Disconnect = lambda *args: None

    def __init__(self, vtmodule):
        self.vtmodule = vtmodule

    def Open(self):
        return GenericReadOnlyVTCursor(self.vtmodule)

    def _readonly(self, *args):
        raise apsw.ReadOnlyError()

    UpdateChangeRow = UpdateDeleteRow = UpdateInsertRow = _readonly


class GenericReadOnlyVTCursor(object):
    Close = lambda *args: None

    def __init__(self, vtmodule):
        self.vtmodule = vtmodule

    def Column(self, number):
        if number == -1:
            return self.Rowid()
        column_type = self.vtmodule.types[number]
        value = self.vtmodule.values[self.position][number]
        if value is not None:
            return column_type(value)

    def Eof(self):
        return self.position >= len(self.vtmodule.values)

    def Filter(self, *args):
        self.position = 0

    def Next(self):
        self.position += 1

    def Rowid(self):
        return self.position
