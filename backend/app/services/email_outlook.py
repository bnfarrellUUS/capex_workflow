"""Send mail through the locally-installed Outlook desktop app via COM.

This is the "for now" backend for local Windows runs: it drives the Outlook
profile the user is already signed into, so no SMTP credentials or Azure app
registration are needed. It only works while the app runs on a Windows machine
with Outlook installed. When the app moves to a server, replace this module
with an SMTP or Microsoft Graph backend — services/notify.py is the only caller.
"""


import os
import re

from app.services import email_frame

_ASSETS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "assets"))

# MAPI property for an attachment's Content-ID (PR_ATTACH_CONTENT_ID), so the
# HTML can reference inline images as <img src="cid:...">.
_PR_ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"

_CID_RE = re.compile(rf"cid:{email_frame.CID_PREFIX}([a-z0-9-]+)")


def _attach_inline_assets(mail, html):
    """Attach every brand asset the HTML references, keyed by Content-ID."""
    for name in sorted(set(_CID_RE.findall(html))):
        filename = email_frame.ASSET_FILES.get(name)
        if not filename:
            continue
        att = mail.Attachments.Add(os.path.join(_ASSETS_DIR, filename))
        att.PropertyAccessor.SetProperty(
            _PR_ATTACH_CONTENT_ID, f"{email_frame.CID_PREFIX}{name}")


def send(to, subject, body, html=None):
    # Imported lazily so the app (and CI on non-Windows) never needs pywin32
    # unless email is actually being sent.
    import pythoncom
    import win32com.client

    pythoncom.CoInitialize()
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
        mail = outlook.CreateItem(0)  # 0 = olMailItem
        mail.To = to
        mail.Subject = subject
        if html is not None:
            _attach_inline_assets(mail, html)
            mail.HTMLBody = html
        else:
            mail.Body = body
        mail.Send()
    finally:
        pythoncom.CoUninitialize()
