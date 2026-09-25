"""Send mail through SendGrid's v3 API -- the sender for a deployed server.

Selected by EMAIL_BACKEND=sendgrid (services/notify.py picks between this and
email_outlook.py). Same send() signature as the Outlook sender, and the same
HTML: the brand PNGs travel as inline attachments under their Content-ID, so
the cid: references in the frame render exactly as they do from Outlook.

Called directly with the standard library rather than through the SendGrid
SDK: the API is a single JSON POST, and every test replaces _post, so nothing
here needs the network or an extra dependency.

THE FROM-ADDRESS IS THE THING TO CHECK WHEN MAIL VANISHES. SendGrid accepts a
send from an unverified sender with a 202 and then drops it, so every log here
records a success. EMAIL_FROM must be an address verified in SendGrid.
"""

import base64
import json
import mimetypes
import os
import urllib.error
import urllib.request

from flask import current_app

from app.services import email_frame

API_URL = "https://api.sendgrid.com/v3/mail/send"

# The SendGrid account is shared with other apps; tag every send so CAPRI's
# traffic stays separable in SendGrid's own reporting.
CATEGORY = "capri"


def _post(url, payload, headers):
    """POST and return (status, body). The single network seam tests replace."""
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def _attachment(filename, data, content_id=None):
    att = {
        "content": base64.b64encode(data).decode(),
        "filename": filename,
        "type": mimetypes.guess_type(filename)[0] or "application/octet-stream",
        "disposition": "inline" if content_id else "attachment",
    }
    if content_id:
        att["content_id"] = content_id
    return att


def send(to, subject, body, html=None, attachments=None):
    """Send one message. `attachments` is a list of (filename, bytes) sent as
    ordinary downloads; the brand images `html` references go inline.
    Raises RuntimeError when SendGrid does not accept the message."""
    cfg = current_app.config
    files = []
    if html is not None:
        content = [{"type": "text/html", "value": html}]
        for content_id, path in email_frame.inline_assets(html):
            with open(path, "rb") as fh:
                files.append(_attachment(os.path.basename(path), fh.read(), content_id))
    else:
        content = [{"type": "text/plain", "value": body}]
    files += [_attachment(name, data) for name, data in attachments or []]

    message = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": cfg["EMAIL_FROM"], "name": cfg.get("EMAIL_FROM_NAME") or "CAPRI"},
        "subject": subject,
        "content": content,
        "categories": [CATEGORY],
    }
    if files:
        message["attachments"] = files

    status, response = _post(API_URL, json.dumps(message).encode(), {
        "Authorization": f"Bearer {cfg['SENDGRID_API_KEY']}",
        "Content-Type": "application/json",
    })
    if status >= 300:
        raise RuntimeError(f"SendGrid returned {status}: {response[:300]!r}")
