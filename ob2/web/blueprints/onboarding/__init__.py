import binascii
import logging
from flask import Blueprint, redirect, render_template, request, session, url_for
from functools import wraps

import ob2.config as config
from ob2.database import DbCursor
from ob2.database.helpers import (
    get_photo,
    get_user_by_id,
    get_user_by_github,
    get_user_by_student_id,
)
from ob2.mailer import create_email, mailer_queue
from ob2.repomanager import repomanager_queue
from ob2.util.authentication import authenticate_as_user, user_id
from ob2.util.github_login import (
    AuthenticationTemporaryError,
    AuthenticationIntegrityError,
    authentication_provider_get_token,
    authenticate_as_github_username,
    get_authentication_provider_url,
    get_username_from_token,
    github_username,
    is_ta,
)
from ob2.util.inst_account import get_inst_account_form_path
from ob2.util.validation import fail_validation, ValidationError, redirect_with_error

blueprint = Blueprint("onboarding", __name__, template_folder="templates")


def _get_current_step():
    if is_ta():
        return "ta.index"
    if user_id():
        return "dashboard.index"
    github = github_username()
    if not github:
        return "onboarding.log_in"
    with DbCursor() as c:
        user = get_user_by_github(c, github)
        if not user:
            return "onboarding.student_id"
        user_id_, _, _, _, _, _ = user
        if config.student_photos_enabled:
            photo = get_photo(c, user_id_)
            if not photo:
                return "onboarding.photo"
        authenticate_as_user(user_id_)
        return "dashboard.index"


def _get_next_step(current_step):
    # I know this kind of logic requires O(2^N) different cases, but right now there's only 1 config
    # option that affects this list (it's the student photos enable/disable), so it's simplest to
    # express the 2 alternatives this way.
    #
    # When we add more features to the onboarding process, you can come up with a better,
    # generalized way of determining the onboarding steps.
    if config.student_photos_enabled:
        steps = ["onboarding.student_id", "onboarding.photo"]
    else:
        steps = ["onboarding.student_id"]

    if current_step is None:
        return steps[0]
    step_i = steps.index(current_step)
    if step_i == len(steps) - 1:
        # This is the final step of onboarding.
        # Authenticate the user and redirect them to the dashboard.
        with DbCursor() as c:
            user = get_user_by_github(c, github_username())
        assert user
        user_id_, _, _, _, _, _ = user
        authenticate_as_user(user_id_)
        return "onboarding.welcome"
    else:
        return steps[step_i + 1]


def _onboarding_redirect(permitted_steps=None):
    """
    If the user is a TA or a fully-onboarded user, then redirect them.
    If the user is already authenticated with GitHub, then redirect them to the correct step in the
    process.

        permitted_steps -- A list of states that this function correctly renders. The user will not
                            be redirected if they are in one of these states. By default, this is a
                            list containing just the name of the wrapped function.

    Consistency note: This wrapper uses a separate database transaction than the one that may be in
    the wrapped function itself. This redirection system should be used for convenience, not to
    ensure any properties about the visitor. Consider, for example, a user who opens the same
    onboarding page on multiple tabs. Wrapped functions should NOT exhibit incorrect behavior when
    this function fails to perform the correct redirection.

    """

    if not permitted_steps:
        permitted_steps = []

    def wrapper(fn):
        if not permitted_steps:
            permitted_steps.append("onboarding.%s" % fn.__name__)

        @wraps(fn)
        def wrapped(*args, **kwargs):
            current_step = _get_current_step()
            if current_step in permitted_steps:
                return fn(*args, **kwargs)
            else:
                return redirect(url_for(current_step))

        return wrapped

    return wrapper


@blueprint.route("/log_in/")
@_onboarding_redirect()
def log_in():
    continue_url = url_for("onboarding.oauth_continue", _external=True)
    return render_template("onboarding/log_in.html",
                           next_step=get_authentication_provider_url(continue_url))


@blueprint.route("/log_in/oauth_continue/")
@_onboarding_redirect(permitted_steps=["onboarding.log_in"])
def oauth_continue():
    if "code" not in request.args or "state" not in request.args:
        return redirect(url_for("onboarding.log_in"))
    code, state = request.args["code"], request.args["state"]
    try:
        try:
            token = authentication_provider_get_token(code, state)
            github = get_username_from_token(token)
        except AuthenticationIntegrityError:
            raise ValidationError("OAuth session expired. Please try again.")
        except AuthenticationTemporaryError:
            logging.exception("Something odd occurred with GitHub OAuth")
            raise ValidationError("GitHub temporary OAuth issue. Please try again.")
    except ValidationError as e:
        return redirect_with_error(url_for("onboarding.log_in"), e)
    authenticate_as_github_username(github)

    # Route the user to the correct onboarding step.
    # OR, if they've finished onboarding, take them to the dashboard.
    # _get_current_step() will perform student dashboard authentication if onboarding is complete.
    current_step = _get_current_step()
    if current_step == "ta.index" and "login_next__ta" in session:
        return redirect(session.pop("login_next__ta"))
    elif current_step == "dashboard.index" and "login_next__dashboard" in session:
        return redirect(session.pop("login_next__dashboard"))
    else:
        return redirect(url_for(current_step))


@blueprint.route("/onboarding/student_id/", methods=["GET", "POST"])
@_onboarding_redirect()
def student_id():
    github = github_username()
    if request.method == "GET":
        return render_template("onboarding/student_id.html",
                               github=github)
    try:
        mailer_job = None
        github_job = None
        with DbCursor() as c:
            user = get_user_by_github(c, github)
            if user:
                return redirect(url_for("dashboard.index"))
            student_id = request.form.get("f_student_id")
            if not student_id:
                fail_validation("Student ID is required")
            user = get_user_by_student_id(c, student_id)
            if not user:
                fail_validation("Student not found with that student ID")
            user_id, name, _, login, old_github, email = user
            if old_github:
                fail_validation("Another GitHub account has been associated with that student "
                                "ID already.")
            if not name:
                fail_validation("There is no name associated with this account. (Contact your TA?)")
            if not login:
                fail_validation("There is no login associated with this account. (Contact your "
                                "TA?)")
            if not email:
                fail_validation("There is no email associated with this account. (Contact your "
                                "TA?)")
            c.execute('''UPDATE users SET github = ? WHERE sid = ?''',
                      [github, student_id])
            if not config.github_read_only_mode:
                github_job = repomanager_queue.create(c, "assign_repo", (login, [github]))
            if config.mailer_enabled:
                if config.inst_account_enabled:
                    attachments = [("pdf", get_inst_account_form_path(login))]
                else:
                    attachments = []
                email_payload = create_email("onboarding_confirm", email,
                                             "%s Autograder Registration" % config.course_number,
                                             _attachments=attachments, name=name, login=login,
                                             inst_account_enabled=config.inst_account_enabled)
                mailer_job = mailer_queue.create(c, "send", email_payload)
        if config.mailer_enabled and mailer_job:
            mailer_queue.enqueue(mailer_job)
        if not config.github_read_only_mode and github_job:
            repomanager_queue.enqueue(github_job)
        return redirect(url_for(_get_next_step("onboarding.student_id")))
    except ValidationError as e:
        return redirect_with_error(url_for("onboarding.student_id"), e)


if config.student_photos_enabled:
    @blueprint.route("/onboarding/photo/", methods=["GET", "POST"])
    @_onboarding_redirect()
    def photo():
        github = github_username()
        if request.method == "GET":
            return render_template("onboarding/photo.html",
                                   github=github)
        try:
            with DbCursor() as c:
                user = get_user_by_github(c, github)
                user_id, _, _, _, _, _ = user
                photo_base64 = request.form.get("f_photo_cropped")
                photo_prefix = "data:image/jpeg;base64,"
                if not photo_base64:
                    fail_validation("No photo submitted. Please choose a photo.")
                if not photo_base64.startswith(photo_prefix):
                    fail_validation("Unrecognized photo format. (Potential autograder bug?)")
                photo_binary = buffer(binascii.a2b_base64(photo_base64[len(photo_prefix):]))
                if len(photo_binary) > 2**21:
                    fail_validation("Photo exceeds maximum allowed size (2MiB).")
                c.execute("UPDATE users SET photo = ? WHERE id = ?", [photo_binary, user_id])
            return redirect(url_for(_get_next_step("onboarding.photo")))
        except ValidationError as e:
            return redirect_with_error(url_for("onboarding.photo"), e)


@blueprint.route("/onboarding/welcome/")
@_onboarding_redirect(["dashboard.index"])
def welcome():
    github = github_username()
    with DbCursor() as c:
        user = get_user_by_id(c, user_id())
    return render_template("onboarding/welcome.html",
                           github=github,
                           user=user,
                           inst_account_enabled=config.inst_account_enabled)


@blueprint.route("/log_out/", methods=["GET", "POST"])
def log_out():
    if request.method == "POST":
        authenticate_as_user(None)
        authenticate_as_github_username(None)
        return redirect(url_for("onboarding.log_in"))
    elif github_username() or user_id():
        return render_template("onboarding/log_out.html")
    else:
        return redirect(url_for("onboarding.log_in"))
