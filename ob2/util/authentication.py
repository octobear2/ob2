from flask import Flask, session

import ob2.config as config
import os

Flask.session_cookie_name = config.flask_cookie_name
if config.flask_secret_key:
    Flask.secret_key = config.flask_secret_key
else:
    # If no secret key is provided, the only sane default we can use is random bytes.
    Flask.secret_key = os.urandom(32)


def user_id():
    return session.get("effective_user_id")


def authenticate_as_user(user_id):
    """Logs in current visitor. Calling this function with None will clear the login token."""
    if user_id:
        session["effective_user_id"] = user_id
    elif "effective_user_id" in session:
        del session["effective_user_id"]
