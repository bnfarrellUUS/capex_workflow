"""Send mail through the locally-installed Outlook desktop app via COM.

This is the "for now" backend for local Windows runs: it drives the Outlook
profile the user is already signed into, so no SMTP credentials or Azure app
registration are needed. It only works while the app runs on a Windows machine
with Outlook installed. When the app moves to a server, replace this module
with an SMTP or Microsoft Graph backend — services/notify.py is the only caller.
"""


import os

from app.services import email_frame

_LOGO_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "assets", "email_logo.png"))

# MAPI property for an attachment's Content-ID (PR_ATTACH_CONTENT_ID), so the
# HTML can reference the inline logo as <img src="cid:...">.
_PR_ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"


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
            if f"cid:{email_frame.LOGO_CID}" in html:
                att = mail.Attachments.Add(_LOGO_PATH)
                att.PropertyAccessor.SetProperty(
                    _PR_ATTACH_CONTENT_ID, email_frame.LOGO_CID)
            mail.HTMLBody = html
        else:
            mail.Body = body
        mail.Send()
    finally:
        pythoncom.CoUninitialize()
