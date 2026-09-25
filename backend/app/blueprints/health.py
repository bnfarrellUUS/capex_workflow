import os

from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from app.extensions import db
from app.services import settings_service
from app.services.sso_service import sso_config

bp = Blueprint("health", __name__)


@bp.get("/api/health")
def health():
    """Liveness plus the MODE each deployment setting selected.

    Never returns a configuration value -- no connection string, host,
    recipient or secret. The modes are here because a missing setting falls
    back to a default that still answers "ok" (APEX Dev ran for a day on an
    empty database of its own that way); these make the difference visible
    from outside. 503 when the database is unreachable, since that deploy
    should not keep serving traffic.
    """
    try:
        db.session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:  # noqa: BLE001 - any failure means "not ok"
        db.session.rollback()
        database = "error"

    email_mode = "unknown"
    if database == "ok":
        try:
            email_mode = settings_service.get_email_settings()["mode"]
        except Exception:  # noqa: BLE001 - e.g. schema not migrated yet
            db.session.rollback()

    body = {
        "status": "ok" if database == "ok" else "error",
        "database": database,
        "db_backend": db.engine.dialect.name,  # "mssql" or "sqlite"
        "email_backend": (current_app.config.get("EMAIL_BACKEND") or "outlook")
                         if current_app.config.get("EMAIL_ENABLED") else "off",
        "email_mode": email_mode,
        "sso": "on" if sso_config() else "off",
        "telemetry": "on" if current_app.config.get("CAPRI_TELEMETRY") else "off",
        "version": os.environ.get("CAPRI_VERSION", "dev"),
    }
    return jsonify(body), 200 if database == "ok" else 503
