import logging
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid
from flask import url_for
from jinja2 import Environment, PackageLoader
from os.path import basename
from werkzeug.urls import url_unparse

import ob2.config as config
from ob2.database import DbCursor
from ob2.util.hooks import apply_filters
from ob2.util.templating import JINJA_EXPORTS
from ob2.util.resumable_queue import ResumableQueue


jinja_environment = None
app = None


def send_template(*args, **kwargs):
    """
    Enqueues an email to be sent on the background thread. See docstring for create_email for
    arguments.

    """
    if not config.mailer_enabled:
        raise RuntimeError("Cannot send mail while mailer is disabled")
    email = create_email(*args, **kwargs)
    with DbCursor() as c:
        job = mailer_queue.create(c, "send", email)
    mailer_queue.enqueue(job)


def create_email(_template_name, _to, _subject, _from=None, _attachments=[],
                 _message_id=None, **kwargs):
    """
    Prepares an email to be sent by the email queue background thread. Templates are taken from
    templates/*.html and templates/*.txt. Both a HTML and a plain text template is expected to be
    present. Parameters should be passed as keyword arguments to this function.

        _template_name
        _to
        _subject
        _from
        _attachments     -- Tuples of (type, file_path) where type should be "pdf" (only pdfs are
                            supported right now)
        _message_id      -- If this message is a REPLY, then specify the message ID(s) of the
                            previous messages in this chain.

    Returns an opaque object (spoiler: it's a tuple) which should be passed directly to
    mailer_queue.enqueue().

    """
    if not config.mailer_enabled:
        raise RuntimeError("Cannot create mail while mailer is disabled")
    if _from is None:
        _from = config.mailer_from
    msg = MIMEMultipart('alternative')
    msg['Subject'] = _subject
    msg['From'] = _from
    msg['To'] = _to
    msg['Message-Id'] = make_msgid()
    if _message_id:
        msg['References'] = _message_id
        msg['In-Reply-To'] = _message_id
    body_plain = render_template("%s.txt" % _template_name, **kwargs)
    body_html = render_template("%s.html" % _template_name, **kwargs)
    msg.attach(MIMEText(body_plain, 'plain', 'utf-8'))
    msg.attach(MIMEText(body_html, 'html', 'utf-8'))
    for attachment_type, attachment_path in _attachments:
        attachment_name = basename(attachment_path)
        with open(attachment_path, "rb") as attachment_file:
            attachment_bytes = attachment_file.read()
        if attachment_type == "pdf":
            attachment = MIMEApplication(attachment_bytes, _subtype="pdf")
            attachment.add_header("Content-Disposition", "attachment", filename=attachment_name)
            msg.attach(attachment)
        else:
            raise ValueError("Unsupported attachment type: %s" % attachment_type)
    return _from, _to, msg.as_string()


def get_jinja_environment():
    global jinja_environment
    if jinja_environment is None:
        jinja_environment = Environment(loader=PackageLoader("ob2.mailer", "templates"))
        jinja_environment.globals.update(JINJA_EXPORTS)
        jinja_environment.globals["url_for"] = url_for
    return jinja_environment


def render_template(template_file_name, **kwargs):
    if app is None:
        raise RuntimeError("No web application registered with mailer")
    template = get_jinja_environment().get_template(template_file_name)
    base_url = url_unparse(("https" if config.web_https else "http",
                            config.web_public_host, "/", "", ""))
    with app.test_request_context(base_url=base_url):
        return template.render(**kwargs)


def register_app(app_):
    """
    Sets the global web application `app`, for use in generating external web URLs for email
    templates. We cannot import this directly, because it creates a cyclic dependency.

    """
    global app
    if app is not None:
        raise ValueError("Mailer global app has already been initialized")
    app = app_


class MailerQueue(ResumableQueue):
    queue_name = "mailerqueue"
    database_table = "mailerqueue"

    def process_job(self, operation, payload):
        """
        Connects to the configured SMTP server using connect_to_smtp defined in config/algorithms
        and sends an email.

        """
        if operation == "send":
            # This is a useful hook for changing the SMTP server that is used by the mail queue. You
            # can, for example, connect to a 3rd party email relay to send emails. You can also just
            # connect to 127.0.0.1 (there's a mail server running on most of the INST servers).
            #
            # Arguments:
            #   smtp_server -- A smtplib.SMTP() object.
            #
            # Returns:
            #   An smtplib.SMTP() object (or compatible) that can be used to send mail.
            smtp_server = apply_filters("connect-to-smtp", smtplib.SMTP())

            smtp_server.sendmail(*payload)
            smtp_server.quit()
        else:
            logging.warning("Unknown operation requested in mailerqueue: %s" % operation)


mailer_queue = MailerQueue()


def main():
    mailer_queue.run()
