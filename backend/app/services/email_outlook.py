"""Send mail through the locally-installed Outlook desktop app via COM.

This is the "for now" backend for local Windows runs: it drives the Outlook
profile the user is already signed into, so no SMTP credentials or Azure app
registration are needed. It only works while the app runs on a Windows machine
with Outlook installed. When the app moves to a server, replace this module
with an SMTP or Microsoft Graph backend — services/notify.py is the only caller.
"""


def send(to, subject, body):
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
        mail.Body = body
        mail.Send()
    finally:
        pythoncom.CoUninitialize()
