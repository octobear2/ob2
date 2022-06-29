import apsw
import logging
import re
import threading
import traceback
from collections import deque

import ob2.config as config
from ob2.database import DbCursor
from ob2.database.helpers import (
    assign_grade_batch,
    get_repo_owners,
    get_users_by_ids,
)
from ob2.dockergrader.job import JobFailedError
from ob2.dockergrader.queue import dockergrader_queue
from ob2.mailer import send_template
from ob2.util.build_constants import QUEUED, IN_PROGRESS, SUCCESS, FAILED
from ob2.util.config_data import get_assignment_by_name
from ob2.util.hooks import get_job
from ob2.util.time import now, now_str, slip_units


class Worker(object):
    def __init__(self):
        self.lock = threading.Lock()
        self.log = deque(maxlen=100)
        self.status = None
        self.updated = now()
        self.identifier = dockergrader_queue.register_worker(self)
        self.thread = threading.current_thread()

    def probe(self, with_log=False):
        with self.lock:
            if with_log:
                return self.identifier, self.status, self.updated, list(self.log)
            else:
                return self.identifier, self.status, self.updated

    def _log(self, message, exc=False):
        payload = (now(), message)
        if exc:
            payload += (traceback.format_exc(),)
        else:
            payload += (None,)
        with self.lock:
            self.log.append(payload)

    def _dequeue_job(self):
        with self.lock:
            self.status = None
            self.updated = now()
        self._log("Waiting for a new job to run")
        return dockergrader_queue.dequeue()

    def _sanitize_name(self, name):
        return re.sub(r'[^a-zA-Z0-9]+', '_', name)

    def _process_job(self, job):
        build_name = job.build_name
        description = job.trigger
        with self.lock:
            self.status = build_name
            self.updated = now()

        assignment = None

        # Mark the job as In Progress
        while True:
            try:
                with DbCursor() as c:
                    c.execute('''SELECT source, `commit`, message, job, started FROM builds
                                 WHERE build_name = ? AND status = ? LIMIT 1''',
                              [build_name, QUEUED])
                    row = c.fetchone()
                    if row is None:
                        self._log("Build %s was missing from the database. Skipping." % build_name)
                        return
                    source, commit, message, job_name, started = row
                    owners = get_repo_owners(c, source)

                    assignment = get_assignment_by_name(job_name)
                    assignment = assignment.student_view(c, source)

                    owner_emails = {owner: email for owner, (_, _, _, _, _, email)
                                    in get_users_by_ids(c, owners).items()}
                    c.execute("UPDATE builds SET status = ?, updated = ? WHERE build_name = ?",
                              [IN_PROGRESS, now_str(), build_name])
                    break
            except apsw.Error:
                self._log("Exception raised while setting status to IN_PROGRESS. Retrying...",
                          exc=True)
                logging.exception("Failed to retrieve next dockergrader job")

        self._log("Started building %s" % build_name)
        try:
            # if the job doesn't exist for some reason, the resulting TypeError will be caught
            # and logged
            due_date = assignment.due_date
            job_handler = get_job(job_name)
            log, score = job_handler(source, commit)
            # log is of type 'bytes'
            min_score, max_score = assignment.min_score, assignment.max_score
            full_score = assignment.full_score
            if score < min_score or score > max_score:
                raise ValueError("A score of %s is not in the acceptable range of %f to %f" %
                                 (str(score), min_score, max_score))
        except JobFailedError as e:
            self._log("Failed %s with JobFailedError" % build_name, exc=True)
            with DbCursor() as c:
                c.execute('''UPDATE builds SET status = ?, updated = ?, log = ?
                             WHERE build_name = ?''', [FAILED, now_str(), str(e), build_name])
            if config.mailer_enabled:
                try:
                    for owner in owners:
                        email = owner_emails.get(owner)
                        if not email:
                            continue
                        subject = "%s failed to complete" % build_name
                        send_template("build_failed", email, subject, build_name=build_name,
                                      job_name=job_name, source=source, commit=commit,
                                      message=message, error_message=str(e))
                except Exception:
                    self._log("Exception raised while reporting JobFailedError", exc=True)
                    logging.exception("Exception raised while reporting JobFailedError")
                else:
                    self._log("JobFailedError successfully reported via email")
            return
        except KeyboardInterrupt as e:
            self._log("Manually interrupted build %s" % build_name, exc=True)
            logging.exception("Manually interrupted build %s" % build_name)
            with DbCursor() as c:
                c.execute('''UPDATE builds SET status = ?, updated = ?, log = ?
                             WHERE build_name = ?''',
                          [FAILED, now_str(), "Build interrupted.", build_name])
            return
        except Exception as e:
            self._log("Exception raised while building %s" % build_name, exc=True)
            logging.exception("Internal error within build %s" % build_name)
            with DbCursor() as c:
                c.execute('''UPDATE builds SET status = ?, updated = ?, log = ?
                             WHERE build_name = ?''',
                          [FAILED, now_str(), "Build failed due to an internal error.", build_name])
            return

        self._log("Autograder build %s complete (score: %s)" % (build_name, str(score)))

        while True:
            try:
                with DbCursor() as c:
                    c.execute('''UPDATE builds SET status = ?, score = ?, updated = ?,
                                 log = ? WHERE build_name = ?''',
                              [SUCCESS, score, now_str(), log, build_name])
                    slipunits = slip_units(due_date, started)
                    if job.graded:
                        affected_users = assign_grade_batch(c, owners, job_name, float(score),
                                                            slipunits, build_name, description,
                                                            "autograder",
                                                            dont_lower=config.use_max_score_build)
                    else:
                        affected_users = []
                    break
            except apsw.Error:
                self._log("Exception raised while assigning grades", exc=True)
                logging.exception("Failed to update build %s after build completed" % build_name)
                return

        if config.mailer_enabled:
            try:
                for owner in owners:
                    email = owner_emails.get(owner)
                    if not email:
                        continue
                    subject = "%s complete - score %s / %s" % (build_name, str(score),
                                                               str(full_score))
                    if owner not in affected_users:
                        subject += " (no effect on grade)"
                    else:
                        if slipunits == 1:
                            subject += " (1 %s used)" % config.slip_unit_name_singular
                        elif slipunits > 0:
                            subject += " (%s slip %s used)" % (str(slipunits),
                                                               config.slip_unit_name_plural)
                    send_template("build_finished", email, subject, build_name=build_name,
                                  job_name=job_name, score=score, full_score=str(full_score),
                                  slipunits=slipunits, log=log, source=source, commit=commit,
                                  message=message, affected=(owner in affected_users))
            except Exception:
                self._log("Exception raised while reporting grade", exc=True)
                logging.exception("Exception raised while reporting grade")
            else:
                self._log("Grade successfully reported via email")

    def run(self):
        while True:
            job = self._dequeue_job()
            self._process_job(job)
