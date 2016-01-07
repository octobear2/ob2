import apsw
import json
import logging
from flask import Blueprint, abort, request

from ob2.database import DbCursor
from ob2.database.helpers import create_build
from ob2.dockergrader import dockergrader_queue, Job
from ob2.util.github_api import get_commit_message, get_diff_file_list
from ob2.util.hooks import apply_filters

blueprint = Blueprint("pushhook", __name__, template_folder="templates")


@blueprint.route("/pushhook/", methods=["POST"])
def pushhook():
    payload_bytes = request.get_data()
    if request.form.get("_csrf_token"):
        # You should not be able to use a CSRF token for this
        abort(400)
    try:
        payload = json.loads(payload_bytes)
        assert isinstance(payload, dict)
        if payload.get("action", "push") != "push":
            logging.warning("Dropped GitHub pushhook payload because action was %s" %
                            str(payload.get("action")))
            return ('', 204)
        ref = payload["ref"]
        before = payload["before"]
        after = payload["after"]
        assert isinstance(ref, basestring)
        assert isinstance(before, basestring)
        assert isinstance(after, basestring)
        repo_name = payload["repository"]["name"]
        assert isinstance(repo_name, basestring)
        file_list = get_diff_file_list(repo_name, before, after)
        if not file_list:
            file_list = []

        # This is a useful hook to use, if you want to add custom logic to determine which jobs get
        # run on a Git push.
        #
        # Arguments:
        #   jobs           -- The original list of jobs (default: empty list)
        #   repo_name      -- The name of the repo that caused the pushhook
        #   ref            -- The name of the ref that was pushed (e.g. "refs/heads/master")
        #   modified_files -- A list of files that were changed in the push, relative to repo root
        #
        # Returns:
        #   A list of job names. (e.g. ["hw0", "hw0-style-check"])
        jobs_to_run = apply_filters("pushhooks-jobs-to-run", [], repo_name, ref, file_list)

        if not jobs_to_run:
            return ('', 204)

        # We could probably grab this from the payload, but let's call this method for the sake
        # of consistency.
        message = get_commit_message(repo_name, after)

        for job_to_run in jobs_to_run:
            while True:
                try:
                    with DbCursor() as c:
                        build_name = create_build(c, job_to_run, repo_name, after, message)
                    break
                except apsw.Error:
                    logging.exception("Failed to create build, retrying...")
            job = Job(build_name, repo_name, "GitHub push")
            dockergrader_queue.enqueue(job)
        return ('', 204)
    except Exception:
        logging.exception("Error occurred while processing GitHub pushhook payload")
        abort(500)
