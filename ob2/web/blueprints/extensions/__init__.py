import apsw
import json
import logging
from flask import Blueprint, abort, request

from ob2.database import DbCursor
from ob2.database.helpers import create_build
from ob2.dockergrader import dockergrader_queue, Job
from ob2.util.github_api import get_commit_message, get_diff_file_list
from ob2.util.hooks import apply_filters
from ob2.util.job_limiter import rate_limit_fail_build, should_limit_source

blueprint = Blueprint("extensions", __name__, template_folder="templates")

@blueprint.route("/extensions/create", methods=["POST"])
def extensions():
    payload_bytes = request.get_data()
    if request.form.get("_csrf_token"):
        # You should not be able to use a CSRF token for this
        abort(400)
    try:
        payload = json.loads(payload_bytes)
        assert isinstance(payload, dict)

        days = int(payload["days"])
        login = payload["login"]

        assert isinstance(days, int)
        assert isinstance(login, str)

        while True:
            try:
                with DbCursor() as c:
                    build_name = create_build(c, job_to_run, repo_name, after, message)
                break
            except apsw.Error:
                logging.exception("Failed to create extension, retrying...")
        if should_limit_source(repo_name, job_to_run):
            rate_limit_fail_build(build_name)
        else:
            job = Job(build_name, repo_name, "Automatic build.")
            dockergrader_queue.enqueue(job)
        return ('', 204)
    except Exception:
        logging.exception("Error occurred while processing create extension request payload")
        abort(500)
