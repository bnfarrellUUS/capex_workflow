import pytest

from app.extensions import db
from app.models import User
from app.services.security import hash_password
from tests.test_sso import FakeMsalApp, sso_env, use_fake


def _user(email="a@x.com", active=True, entra_oid=None, must_change=False):
    u = User(email=email, name="A User", password_hash=hash_password("secret123"),
             roles='["REQUESTOR"]', active=active, entra_oid=entra_oid,
             must_change_password=must_change)
    db.session.add(u)
    db.session.commit()
    return u


def _claims(**over):
    c = {"preferred_username": "a@x.com", "groups": ["group-a"], "oid": "oid-1"}
    c.update(over)
    return c


# ---------------------------------------------------- GET /api/auth/config

def test_config_reports_sso_off_by_default(client):
    r = client.get("/api/auth/config")
    assert r.status_code == 200
    assert r.get_json() == {"ok": True, "sso_enabled": False}


def test_config_reports_sso_on(client, monkeypatch):
    sso_env(monkeypatch)
    assert client.get("/api/auth/config").get_json()["sso_enabled"] is True


def test_config_needs_no_authentication(client, monkeypatch):
    # /api/auth/me 401s before login, so the login screen has no other way to
    # learn which form to draw.
    sso_env(monkeypatch)
    assert client.get("/api/auth/config").status_code == 200


# ------------------------------------ the routes do not exist when SSO is off

@pytest.mark.parametrize("path", ["/api/auth/sso/login", "/api/auth/sso/callback"])
def test_sso_routes_404_when_sso_is_off(client, path):
    # 404, not 403: with the flag off these entry points do not exist.
    assert client.get(path).status_code == 404


# ------------------------------------------------ GET /api/auth/sso/login

def test_sso_login_redirects_to_entra_and_stores_the_flow(client, monkeypatch):
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp())
    r = client.get("/api/auth/sso/login")
    assert r.status_code == 302
    assert r.headers["Location"].startswith("https://login.microsoftonline.com/")
    with client.session_transaction() as sess:
        assert sess["sso_flow"]["state"] == "st"


def test_sso_login_stores_a_safe_next_path(client, monkeypatch):
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp())
    client.get("/api/auth/sso/login?next=/requests/42")
    with client.session_transaction() as sess:
        assert sess["sso_next"] == "/requests/42"


def test_sso_login_discards_an_offsite_next_path(client, monkeypatch):
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp())
    client.get("/api/auth/sso/login?next=//evil.com")
    with client.session_transaction() as sess:
        assert sess["sso_next"] == ""


def test_sso_login_redirects_rather_than_500s_on_an_msal_error(client, monkeypatch):
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp(raises=RuntimeError("entra unreachable")))
    r = client.get("/api/auth/sso/login")
    assert r.status_code == 302
    assert r.headers["Location"] == "/login?sso_error=auth_failed"


# --------------------------------------------- GET /api/auth/sso/callback

def _start_flow(client, monkeypatch, claims=None, raises=None, next_path=None):
    """Drive /sso/login so a real flow is in the session, then fake the redeem."""
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp())
    client.get(f"/api/auth/sso/login?next={next_path}" if next_path
               else "/api/auth/sso/login")
    use_fake(monkeypatch, FakeMsalApp(
        result=None if raises else {"id_token_claims": claims or _claims()},
        raises=raises))


def test_callback_signs_the_user_in(client, monkeypatch):
    _user()
    _start_flow(client, monkeypatch)
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.status_code == 302
    assert r.headers["Location"] == "/"
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["auth_method"] == "sso"


def test_callback_sets_no_remember_cookie(client, monkeypatch):
    # Centralised revocation is much of the point of SSO: a 30-day remember
    # cookie would keep someone in CAPRI for weeks after Entra access was
    # withdrawn. The password path keeps its cookie.
    _user()
    _start_flow(client, monkeypatch)
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert not any(c.startswith("remember_token=")
                   for c in r.headers.getlist("Set-Cookie"))


def test_callback_honours_a_stored_deep_link(client, monkeypatch):
    _user()
    _start_flow(client, monkeypatch, next_path="/requests/42")
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.headers["Location"] == "/requests/42"


def test_callback_consumes_the_flow_so_a_replay_fails(client, monkeypatch):
    # A flow is single-use; leaving it in the session invites replay.
    _user()
    _start_flow(client, monkeypatch)
    assert client.get("/api/auth/sso/callback?code=c&state=st").status_code == 302
    client.post("/api/auth/logout")
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.headers["Location"] == "/login?sso_error=auth_failed"


def test_callback_with_no_flow_in_session_fails_closed(client, monkeypatch):
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp(result={"id_token_claims": _claims()}))
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.headers["Location"] == "/login?sso_error=auth_failed"
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("claims_over,expected", [
    ({"groups": None}, "no_groups_claim"),
    ({"groups": ["other"]}, "not_in_group"),
    ({"preferred_username": "nobody@x.com"}, "unknown_user"),
])
def test_callback_reports_each_gate_with_its_own_code(client, monkeypatch,
                                                      claims_over, expected):
    _user()
    _start_flow(client, monkeypatch, claims=_claims(**claims_over))
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.headers["Location"] == f"/login?sso_error={expected}"
    assert client.get("/api/auth/me").status_code == 401


def test_callback_reports_an_inactive_user(client, monkeypatch):
    _user(active=False)
    _start_flow(client, monkeypatch)
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.headers["Location"] == "/login?sso_error=inactive_user"


def test_callback_reports_an_identity_mismatch(client, monkeypatch):
    _user(entra_oid="oid-original")
    _start_flow(client, monkeypatch)
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.headers["Location"] == "/login?sso_error=identity_mismatch"


def test_callback_never_returns_json_or_leaks_detail(client, monkeypatch):
    # The browser is doing a top-level navigation; a JSON body renders as a
    # blank page with text on it. And the provider's description can quote back
    # attacker-influenced input.
    _user()
    _start_flow(client, monkeypatch, raises=ValueError("AADSTS-secret-detail"))
    r = client.get("/api/auth/sso/callback?code=c&state=st")
    assert r.status_code == 302
    assert r.headers["Location"] == "/login?sso_error=auth_failed"
    assert b"AADSTS" not in r.data


# ----------------------------------------------------------- the password door

def test_password_login_is_403_when_sso_is_on(client, monkeypatch):
    _user()
    sso_env(monkeypatch)
    r = client.post("/api/auth/login", json={"email": "a@x.com", "password": "secret123"})
    assert r.status_code == 403
    assert "Microsoft" in r.get_json()["error"]


def test_password_login_still_works_on_an_incomplete_config(client, monkeypatch):
    # Fail closed on configuration: CAPRI_ENABLE_SSO=1 with a half-filled
    # config is a deployment mistake, and refusing every login over a typo is
    # worse than leaving password login up.
    _user()
    sso_env(monkeypatch, CAPRI_SSO_CLIENT_SECRET=None)
    r = client.post("/api/auth/login", json={"email": "a@x.com", "password": "secret123"})
    assert r.status_code == 200


def test_password_login_reports_its_auth_method(client):
    _user()
    r = client.post("/api/auth/login", json={"email": "a@x.com", "password": "secret123"})
    assert r.get_json()["auth_method"] == "password"
