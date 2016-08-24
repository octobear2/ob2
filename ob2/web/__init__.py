import sys
from cherrypy import wsgiserver
from flask import (
    abort,
    Flask,
    redirect,
    request,
    url_for,
)
from importlib import import_module
from logging import StreamHandler
from werkzeug.contrib.fixers import ProxyFix

import ob2.config as config
import ob2.mailer as mailer
from ob2.util.authentication import user_id
from ob2.util.security import generate_shitty_random_string, get_request_validity
from ob2.util.github_login import is_ta
from ob2.util.templating import JINJA_EXPORTS

app = Flask("ob2.web", static_url_path=("%s/static" % config.web_public_root))
if config.web_behind_proxy:
    app.wsgi_app = ProxyFix(app.wsgi_app)
app.logger.addHandler(StreamHandler(sys.stdout))
app.debug = config.debug_mode
app.config["SESSION_COOKIE_PATH"] = config.web_public_root + "/"
app.config["SESSION_COOKIE_SECURE"] = config.web_https
app.config["SERVER_NAME"] = config.web_public_host
app.jinja_env.globals.update(JINJA_EXPORTS)

# We need to tell our mailer daemon about the web application, so that we can use url_for() to
# generate URL's in our email templates. We can't just import "app" from this module, because that
# would create a cyclic import dependency.
mailer.register_app(app)

cache_buster_hash = generate_shitty_random_string(8)


for blueprint in ("onboarding",
                  "dashboard",
                  "ta",
                  "pushhook"):
    module = import_module("ob2.web.blueprints.%s" % blueprint)
    app.register_blueprint(module.blueprint, url_prefix=config.web_public_root)


@app.url_defaults
def hashed_url_for_static_file(endpoint, values):
    if 'static' == endpoint or endpoint.endswith('.static'):
        filename = values.get('filename')
        if filename:
            param_name = 'ver'
            while param_name in values:
                param_name = '_' + param_name
            values[param_name] = cache_buster_hash


@app.before_request
def _before_request():
    if request.method == "POST":
        # Automatic CSRF protection for all POST-endpoints.
        if not get_request_validity():
            abort(403)


@app.route("%s/" % config.web_public_root)
def site_index():
    if is_ta():
        return redirect(url_for("ta.index"), code=302)
    elif user_id():
        return redirect(url_for("dashboard.index"), code=302)
    else:
        return redirect(url_for("onboarding.log_in"), code=302)


def main():
    server_type = "werkzeug"
    if not config.debug_mode:
        server_type = "cherrypy"
    if config.web_server_type:
        server_type = config.web_server_type

    assert server_type in ("werkzeug", "cherrypy"), "Only werkzeug and cherrypy supported"

    if server_type == "werkzeug":
        assert config.debug_mode, "Refusing to use werkzeug outside of debug mode"
        app.run(config.web_host, config.web_port, debug=True, use_reloader=False, use_debugger=True,
                threaded=True)
    elif server_type == "cherrypy":
        dispatcher = wsgiserver.WSGIPathInfoDispatcher({"/": app})
        web_server = wsgiserver.CherryPyWSGIServer((config.web_host, config.web_port),
                                                   dispatcher,
                                                   server_name=config.web_public_host)
        web_server.start()
