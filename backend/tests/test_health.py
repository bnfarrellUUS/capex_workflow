"""/api/health reports MODES, never configuration values.

Each field answers "did the setting take?" from outside the container. On
APEX Dev a missing setting silently fell back to a working-looking default (an
empty SQLite database, email off) and `status: ok` could not tell the
difference; these fields make it one glance.
"""

from unittest import mock

from sqlalchemy.exc import OperationalError

from app.services import settings_service


def test_health_reports_modes(client, monkeypatch):
    monkeypatch.delenv("CAPRI_VERSION", raising=False)
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json() == {
        "status": "ok",
        "database": "ok",
        "db_backend": "sqlite",
        "email_backend": "off",      # TestConfig has EMAIL_ENABLED = False
        "email_mode": "test",        # settings_service default
        "sso": "off",
        "telemetry": "off",
        "version": "dev",
    }


def test_health_needs_no_sign_in(client):
    assert client.get("/api/health").status_code == 200


def test_health_reports_live_email_mode(app, client):
    settings_service.set_email_settings("live", "x@uniteduptime.com")
    body = client.get("/api/health").get_json()
    assert body["email_mode"] == "live"
    assert "x@uniteduptime.com" not in str(body)  # a value, not a mode


def test_health_reports_version_from_the_image(client, monkeypatch):
    monkeypatch.setenv("CAPRI_VERSION", "1234")
    assert client.get("/api/health").get_json()["version"] == "1234"


def test_health_reports_sso_on(client, monkeypatch):
    for k, v in {"CAPRI_ENABLE_SSO": "1", "CAPRI_SSO_TENANT_ID": "t",
                 "CAPRI_SSO_CLIENT_ID": "c", "CAPRI_SSO_CLIENT_SECRET": "s",
                 "CAPRI_SSO_ALLOWED_GROUPS": "g",
                 "CAPRI_SSO_REDIRECT_URI": "http://localhost:5100/api/auth/sso/callback"}.items():
        monkeypatch.setenv(k, v)
    body = client.get("/api/health").get_json()
    assert body["sso"] == "on"
    assert "s" not in body.values()


def test_health_is_503_when_the_database_is_unreachable(client):
    boom = OperationalError("SELECT 1", {}, Exception("down"))
    with mock.patch("app.blueprints.health.db.session.execute", side_effect=boom):
        resp = client.get("/api/health")
    assert resp.status_code == 503
    body = resp.get_json()
    assert body["status"] == "error"
    assert body["database"] == "error"
    assert body["email_mode"] == "unknown"  # not asserted without a database


def test_liveness_answers_without_the_database(client):
    # ACA restarts a container whose liveness probe fails; a brief Azure SQL
    # failover must not do that (ADO 5908), so /live never touches the DB.
    boom = OperationalError("SELECT 1", {}, Exception("down"))
    with mock.patch("app.blueprints.health.db.session.execute", side_effect=boom) as execute:
        resp = client.get("/api/health/live")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}
    execute.assert_not_called()
