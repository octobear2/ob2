import logging
import signal
import sys
import traceback
from threading import Thread

import ob2.config as config
import ob2.dockergrader
import ob2.mailer
import ob2.repomanager
import ob2.web
from ob2.database.migrations import migrate
from ob2.database.validation import validate_database_constraints
from ob2.dockergrader import reset_grader
from ob2.mailer import mailer_queue
from ob2.repomanager import repomanager_queue
from ob2.util.config_data import validate_config

from ob2.database import DbCursor  # noqa (for --ipython mode)
from ob2.util.github_api import _get_github_admin  # noqa (for --ipython mode)


def main():
    # Runs code in "functions.py" files, provided in configuration directories.
    config.exec_custom_functions()

    # Sets up logging
    if config.debug_mode:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.debug("Setting log level to DEBUG (debug_mode is enabled)")

    # Set up graceful exit for SIGTERM (so finally clauses might have a chance to execute)
    def handle_sigterm(*args):
        logging.warn("Exiting due to SIGTERM")
        sys.exit(0)

    signal.signal(signal.SIGTERM, handle_sigterm)

    # Validates constraints on the configuration data (does not touch database)
    validate_config()

    # Performs database migrations as needed
    migrate()

    # Validates constraints on the configuration data and database data in conjunction
    validate_database_constraints()

    if config.mode == "ipython":
        # If we're running --ipython mode, STOP here (don't interfere with a server that may be
        # running simultaneuosly). Launch the IPython shell and wait for user input.
        import IPython
        return IPython.embed()
    elif config.mode == "server":
        # Run ob2 in server mode.
        #
        # First, we clean up our resumable queues by re-enqueuing any half-completed transactions.
        # Then, we reset the state of the local Docker daemon.
        # Then, we start all our worker threads.
        # Finally, the main thread goes to sleep until we receive a signal.

        # Recovers the resumable queue used for the mailer thread (if mailer is enabled)
        if config.mailer_enabled:
            mailer_queue.recover()

        # Recovers the resumable queue used for the GitHub API thread (if GitHub is NOT in read-only
        # mode)
        if not config.github_read_only_mode:
            repomanager_queue.recover()

        # Clears out stray Docker containers and images
        reset_grader()

        # Start background threads for all the apps
        # Warning: Do not try to start more than 1 web thread. The web server is already threaded.
        apps = [(ob2.dockergrader, 3),
                (ob2.web, 1)]
        if config.mailer_enabled:
            apps.append((ob2.mailer, 1))
        if not config.github_read_only_mode:
            # The GitHub repo manager thread is only needed if GitHub is NOT in read-only mode
            apps.append((ob2.repomanager, 1))
        for app, num_workers in apps:
            for _ in range(num_workers):
                worker = Thread(target=app.main)
                worker.daemon = True
                worker.start()

        # Wait until we're asked to quit
        while True:
            try:
                signal.pause()
            except (KeyboardInterrupt, SystemExit):
                logging.warn("Shutting down.. Goodbye world.")
                break
            except:
                traceback.print_exc()


if __name__ == '__main__':
    main()
