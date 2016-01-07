from ob2.database import DbCursor
from ob2.dockergrader.job import Job
from ob2.dockergrader.queue import dockergrader_queue
from ob2.dockergrader.rpc import DockerClient
from ob2.dockergrader.worker import Worker
from ob2.util.build_constants import FAILED, IN_PROGRESS, QUEUED

__all__ = ["Job", "dockergrader_queue"]


def reset_grader():
    with DbCursor() as c:
        c.execute("UPDATE builds SET status = ? WHERE status in (?, ?)",
                  [FAILED, QUEUED, IN_PROGRESS])
    DockerClient().clean()


def main():
    worker = Worker()
    worker.run()
