import github3
import requests
import urllib
import urlparse
from flask import session

import ob2.config as config
from ob2.util.security import generate_shitty_random_string

github_oauth_url = "https://github.com/login/oauth"
access_token_url = github_oauth_url + "/access_token"
authorize_url = github_oauth_url + "/authorize"
user_url = "https://github.com"


class AuthenticationError(Exception):
    pass


class AuthenticationTemporaryError(AuthenticationError):
    pass


class AuthenticationIntegrityError(AuthenticationError):
    pass


def get_authentication_provider_url(redirect_uri):
    if config.github_oauth_consumer_key:
        state = generate_shitty_random_string()
        session["authentication_oauth_state"] = state

        return "%s?%s" % (authorize_url, urllib.urlencode({
            "client_id": config.github_oauth_consumer_key,
            "redirect_uri": redirect_uri,
            "state": state}))


def authentication_provider_get_token(code, state):
    if not state or session.get("authentication_oauth_state") != state:
        raise AuthenticationIntegrityError("OAuth state parameter does not match")
    response = requests.post(access_token_url,
                             data={"client_id": config.github_oauth_consumer_key,
                                   "client_secret": config.github_oauth_consumer_secret,
                                   "code": code})
    if response.status_code != 200:
        raise AuthenticationTemporaryError("Failed to get OAuth api token from GitHub")
    response_dict = dict(urlparse.parse_qsl(response.text))
    if "access_token" not in response_dict:
        raise AuthenticationTemporaryError("GitHub OAuth response did not contain access_token")

    return response_dict["access_token"]


def get_username_from_token(token):
    github = github3.login(token=token)
    github_user = github.user()
    return github_user.login


def github_username():
    return session.get("github_username")


def authenticate_as_github_username(username):
    if username:
        session["github_username"] = username
    elif "github_username" in session:
        del session["github_username"]


def is_ta():
    username = github_username()
    return username and username in config.github_ta_usernames
