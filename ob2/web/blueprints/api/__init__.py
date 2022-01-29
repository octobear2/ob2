import json
import logging
from flask import Blueprint, abort, request

import smtplib
from base64 import b64decode
from sicp.common.rpc.secrets import validates_master_secret
from sicp.common.rpc.mail import send_email
from email.message import EmailMessage
from mimetypes import guess_type

from ob2.database import DbCursor
from ob2.util.hooks import apply_filters

blueprint = Blueprint("api", __name__, template_folder="templates")

blueprint.add_url_rule("/api/hello_world", "hello_world", lambda: "hello world", methods=["GET", "POST"])

@send_email.bind(blueprint)
@validates_master_secret
def send_email(app, is_staging, sender, target, subject, body, targets = [], attachments = {}, extra_headers = []):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = target
    for k, v in extra_headers:
        msg[k] = v
    msg.set_content(body)
    for attach_name, attach_content in attachments.items():
        ctype, encoding = guess_type(attach_name)
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        msg.add_attachment(
            b64decode(attach_content.encode("ascii")),
            maintype=maintype,
            subtype=subtype,
            filename=attach_name,
        )
    smtp_server = apply_filters("connect-to-smtp", smtplib.SMTP())
    smtp_server.send_message(msg, "cs162ta@cs162.eecs.berkeley.edu", target)
    for target in targets:
        smtp_server.send_message(msg, "cs162ta@cs162.eecs.berkeley.edu", target)
    smtp_server.quit()
    return ('', 202)
# app.add_url_rule("/autograder/api/send_email", "send_email", send_email, methods=["POST"])
