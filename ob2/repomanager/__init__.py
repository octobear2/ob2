import logging

import ob2.config as config
from ob2.util.github_api import _assign_repo
from ob2.util.resumable_queue import ResumableQueue


class Repomanager(ResumableQueue):
    queue_name = "repomanager"
    database_table = "repomanager"

    def process_job(self, operation, payload):
        """
        Processes API requests for GitHub that are NOT read-only.

        """
        if operation == "assign_repo":
            _assign_repo(*payload)
        else:
            logging.warning("Unknown operation requested in repomanager: %s" % operation)


repomanager_queue = Repomanager()


def main():
    if config.github_read_only_mode:
        raise RuntimeError("Cannot start RepoManager thread if we're in GitHub read-only mode")
    repomanager_queue.run()
