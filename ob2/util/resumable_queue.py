import json
import logging
from collections import deque
from threading import Condition

from ob2.database import DbCursor
from ob2.database.helpers import get_next_autoincrementing_value
from ob2.util.time import now_str


class ResumableQueue(object):
    """
    A generic implementation of a job queue that retries jobs until they succeed. Jobs are
    stored in the database so that they persist across crashes.

    """
    queue_name = None
    database_table = None

    def __init__(self):
        assert self.queue_name is not None
        assert self.database_table is not None
        self.queue = deque()
        self.queue_cv = Condition()
        self.recovered = False

    def get_transaction_id(self, c):
        option_key = "%s_next_transaction_id" % self.queue_name
        transaction_id = get_next_autoincrementing_value(c, option_key)
        return transaction_id

    def serialize_arguments(self, payload):
        return json.dumps(payload)

    def unserialize_arguments(self, serialized):
        return json.loads(serialized)

    def create(self, c, operation, payload):
        """
        Creates a new queue job and returns an opaque object representing the job. The new job will
        be part of the transaction, so if the transaction is rolled back, this job will disappear
        too.

        If the transaction is successful, you should pass the opaque object returned by this method
        to enqueue(), so the queue runner can process it. Otherwise, it will be processed during
        the next re-start of the server daemon when uncompleted jobs are retried.

        """
        transaction_id = self.get_transaction_id(c)
        c.execute('''INSERT INTO %s (id, operation, payload, updated, completed)
                     VALUES (?, ?, ?, ?, ?)''' % self.database_table,
                  [transaction_id, operation, self.serialize_arguments(payload), now_str(), 0])
        return (transaction_id, operation, payload)

    def enqueue(self, job_object):
        """
        Enqueues a previously created job. The job will be processed by the queue runner.

        """
        with self.queue_cv:
            self.queue.append(job_object)
            self.queue_cv.notify()

    def recover(self):
        """
        Scans the database for uncompleted jobs and re-enqueues them.

        """
        assert not self.recovered, "ResumableQueue should only be recovered from DB once"
        self.recovered = True
        with DbCursor() as c:
            c.execute('SELECT id, operation, payload FROM %s WHERE completed = 0' %
                      self.database_table)
            with self.queue_cv:
                for transaction_id, operation, payload in c.fetchall():
                    payload = self.unserialize_arguments(payload)
                    self.queue.append((transaction_id, operation, payload))
                self.queue_cv.notify()

    def process_job(self, operation, payload):
        """
        This method should be overridden with an implementation that does something with the job
        payload. It would be a good idea to make this implementation idempotent, because jobs may
        be interrupted or run multiple times.

        """
        pass

    def mark_as_complete(self, transaction_id):
        while True:
            try:
                with DbCursor() as c:
                    c.execute("UPDATE %s SET completed = 1 WHERE id = ?" %
                              self.database_table, [transaction_id])
                    break
            except Exception:
                logging.exception("[%s] Error occurred while marking %s as done" %
                                  (self.queue_name, transaction_id))

    def run(self):
        while True:
            with self.queue_cv:
                while not self.queue:
                    self.queue_cv.wait()
                transaction_id, operation, payload = self.queue.popleft()
            try:
                self.process_job(operation, payload)
            except Exception:
                logging.exception("[%s] Error occurred while processing queue" % self.queue_name)
            else:
                self.mark_as_complete(transaction_id)
