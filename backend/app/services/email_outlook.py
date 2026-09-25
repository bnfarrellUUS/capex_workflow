"""Send mail through the locally-installed Outlook desktop app via COM.

This is the "for now" backend for local Windows runs: it drives the Outlook
profile the user is already signed into, so no SMTP credentials or Azure app
registration are needed. It only works while the app runs on a Windows machine
with Outlook installed. On a server, email_sendgrid.py is used instead
(EMAIL_BACKEND=sendgrid); services/notify.py picks between the two.
"""


from app.services import email_frame

# MAPI property for an attachment's Content-ID (PR_ATTACH_CONTENT_ID), so the
# HTML can reference inline images as <img src="cid:...">.
_PR_ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"


def _attach_inline_assets(mail, html):
    """Attach every brand asset the HTML references, keyed by Content-ID."""
    for content_id, path in email_frame.inline_assets(html):
        att = mail.Attachments.Add(path)
        att.PropertyAccessor.SetProperty(_PR_ATTACH_CONTENT_ID, content_id)


def send(to, subject, body, html=None, attachments=None):
    """Send via Outlook. `attachments` is a list of (filename, bytes) attached
    as ordinary visible files (unlike the inline brand assets, which are keyed
    by Content-ID). Outlook's COM API only attaches from a path, so each one is
    written to a temp file and cleaned up after the send."""
    # Imported lazily so the app (and CI on non-Windows) never needs pywin32
    # unless email is actually being sent.
    import os
    import pythoncom
    import win32com.client
    import shutil
    import tempfile

    tmpdir = tempfile.mkdtemp(prefix="capri-mail-") if attachments else None
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
        for filename, data in attachments or []:
            path = os.path.join(tmpdir, filename)
            with open(path, "wb") as fh:
                fh.write(data)
            mail.Attachments.Add(path)
        mail.Send()
    finally:
        pythoncom.CoUninitialize()
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)
