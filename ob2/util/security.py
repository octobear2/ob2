import hmac
import string
import random
from flask import abort, request, session
from functools import wraps
from hashlib import sha1

import ob2.config as config


# plz no
def generate_shitty_random_string(N=30):
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(N))


def get_request_validity():
    # GitHub signature will suffice for CSRF check
    github_signature = request.headers.get("X-Hub-Signature")
    if github_signature:
        payload_bytes = request.get_data()
        for github_webhook_secret in config.github_webhook_secrets:
            digest = hmac.new(github_webhook_secret, payload_bytes, sha1).hexdigest()
            expected_signature = "sha1=%s" % digest
            if expected_signature == github_signature:
                return True
    # Normal CSRF form tokens work too
    token = request.form.get("_csrf_token")
    expected_token = session.get("_csrf_token", None)
    if expected_token and expected_token == token:
        return True
    return False


def generate_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = generate_shitty_random_string()
    return session["_csrf_token"]


def require_csrf_token(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        token = session.get("_csrf_token", None)
        if not token or token != request.args.get("_csrf_token"):
            abort(403)
        return fn(*args, **kwargs)
    return wrapped
