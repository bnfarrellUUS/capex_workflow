"""App-wide settings stored in the AppSetting key/value table.

Currently the email delivery mode: Test (redirect all notifications to a test
recipient) vs Live (send to the real recipients). Defaults keep the historical
behavior — Test mode redirecting to the app's EMAIL_REDIRECT_TO — until an
admin changes it.
"""
from flask import current_app

from app.extensions import db
from app.models import AppSetting

MODE_KEY = "email_mode"
RECIPIENT_KEY = "email_test_recipient"


def _get(key):
    row = db.session.get(AppSetting, key)
    return row.value if row else None


def _set(key, value):
    row = db.session.get(AppSetting, key)
    if row:
        row.value = value
    else:
        db.session.add(AppSetting(key=key, value=value))


def get_email_settings():
    mode = _get(MODE_KEY) or "test"
    recipient = _get(RECIPIENT_KEY) or current_app.config.get("EMAIL_REDIRECT_TO") or ""
    return {"mode": mode, "test_recipient": recipient}


def set_email_settings(mode, test_recipient):
    _set(MODE_KEY, mode)
    _set(RECIPIENT_KEY, test_recipient)
    db.session.commit()
    return get_email_settings()
