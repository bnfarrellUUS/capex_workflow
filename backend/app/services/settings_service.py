"""App-wide settings stored in the AppSetting key/value table.

Two settings live here. The email delivery mode: Test (redirect all
notifications to a test recipient) vs Live (send to the real recipients);
defaults keep the historical behavior — Test mode redirecting to the app's
EMAIL_REDIRECT_TO — until an admin changes it. And the wizard sections an
admin has hidden, stored as a JSON array; nothing is hidden by default.
"""
import json

from flask import current_app

from app.extensions import db
from app.models import AppSetting

MODE_KEY = "email_mode"
RECIPIENT_KEY = "email_test_recipient"
HIDDEN_SECTIONS_KEY = "wizard_hidden_sections"


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


def get_hidden_sections():
    """Wizard section keys an admin has hidden. Unset or unreadable → none."""
    raw = _get(HIDDEN_SECTIONS_KEY)
    if not raw:
        return []
    try:
        value = json.loads(raw)
    except ValueError:
        return []
    return value if isinstance(value, list) else []


def set_hidden_sections(keys):
    _set(HIDDEN_SECTIONS_KEY, json.dumps(list(keys)))
    db.session.commit()
    return get_hidden_sections()
