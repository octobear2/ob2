from collections import deque
from threading import Condition, Lock


class _DockergraderQueue(object):
    def __init__(self):
        self._queue = deque()
        self._queue_cv = Condition()
        self._workers = []
        self._workers_lock = Lock()

    def enqueue(self, job):
        """
        Adds a job to the queue.

        """
        with self._queue_cv:
            self._queue.append(job)
            self._queue_cv.notify()

    def dequeue(self):
        """
        Takes a job from the queue, or blocks until a job is ready to go.

        """
        with self._queue_cv:
            while not self._queue:
                self._queue_cv.wait()
            return self._queue.popleft()

    def snapshot(self):
        """
        Returns a list containing references to all jobs currently in the queue. Because of Python
        GC semantics, we don't need to worry about synchronization after the list has been
        constructed.

        """
        with self._queue_cv:
            return list(self._queue)

    def register_worker(self, worker):
        """
        Registers a dockergrader worker thread globally. This is used so that we can check the
        status of all workers to see if the queue is stuck.

        Returns a unique worker ID (starting with 1)

        """
        with self._workers_lock:
            self._workers.append(worker)
            return len(self._workers)

    def probe_worker(self, number, with_log=True):
        """
        Returns debugging information for a worker, given its number.

        """
        with self._workers_lock:
            if 1 <= number <= len(self._workers):
                return self._workers[number - 1].probe(with_log=with_log)

    def probe_workers(self, with_log=False):
        """
        Returns debugging information for all registered workers.

        """
        with self._workers_lock:
            return [worker.probe(with_log=with_log) for worker in self._workers]


dockergrader_queue = _DockergraderQueue()
