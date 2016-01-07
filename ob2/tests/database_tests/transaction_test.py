import apsw
import threading
from unittest2 import TestCase

from ob2.database import DbCursor


class TransactionTest(TestCase):
    def test_rollback(self):
        with DbCursor() as c:
            c.execute("DELETE FROM options WHERE key = ?", ["test_value1"])
        with self.assertRaises(ValueError):
            with DbCursor() as c:
                c.execute("INSERT INTO options (key, value) VALUES (?, ?)", ["test_value1", "ok"])
                c.execute("SELECT value FROM options WHERE key = ?", ["test_value1"])
                value, = c.fetchone()
                self.assertEqual(value, "ok")
                raise ValueError("Catch me")
        with DbCursor() as c:
            c.execute("SELECT count(*) FROM options WHERE key = ?", ["test_value1"])
            count, = c.fetchone()
            self.assertEqual(count, 0)

    def test_conflict(self):
        """This test is actually kind of dumb and useless..."""
        with DbCursor() as c:
            c.execute("DELETE FROM options WHERE key = ?", ["test_value1"])
            c.execute("INSERT INTO options (key, value) VALUES (?, ?)", ["test_value1", "ok"])

        ready1 = threading.Event()
        ready2 = threading.Event()

        def job1():
            with DbCursor() as c:
                c.execute("SELECT value FROM options WHERE key = ?", ["test_value1"])
                value, = c.fetchone()
                ready1.set()
                ready2.wait()
                with self.assertRaises(apsw.BusyError):
                    c.execute("UPDATE options SET value = ? WHERE key = ?",
                              [value + "a", "test_value1"])

        def job2():
            with DbCursor() as c:
                c.execute("SELECT value FROM options WHERE key = ?", ["test_value1"])
                value, = c.fetchone()
                ready1.wait()
                c.execute("UPDATE options SET value = ? WHERE key = ?",
                          [value + "y", "test_value1"])
                ready2.set()

        thread1 = threading.Thread(target=job1)
        thread2 = threading.Thread(target=job2)
        thread1.start()
        thread2.start()
        thread1.join()
        thread2.join()

        with DbCursor() as c:
            c.execute("SELECT value FROM options WHERE key = ?", ["test_value1"])
            value, = c.fetchone()
            c.execute("DELETE FROM options WHERE key = ?", ["test_value1"])
            self.assertEqual("oky", value)
