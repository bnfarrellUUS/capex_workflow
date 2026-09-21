import pytest

from app.services import sso_service


def sso_env(monkeypatch, **overrides):
    """Put a complete, valid SSO config in the environment.

    Pass a keyword as None to remove that variable, which is how the
    fail-closed cases below drop one value at a time.
    """
    values = {
        "CAPRI_ENABLE_SSO": "1",
        "CAPRI_SSO_TENANT_ID": "tenant-guid",
        "CAPRI_SSO_CLIENT_ID": "client-guid",
        "CAPRI_SSO_CLIENT_SECRET": "shh",
        "CAPRI_SSO_ALLOWED_GROUPS": "group-a,group-b",
        "CAPRI_SSO_REDIRECT_URI": "http://localhost:5100/api/auth/sso/callback",
    }
    values.update(overrides)
    for key, value in values.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)


def test_config_is_none_without_the_flag(monkeypatch):
    sso_env(monkeypatch, CAPRI_ENABLE_SSO=None)
    assert sso_service.sso_config() is None


def test_config_is_none_when_the_flag_is_not_exactly_one(monkeypatch):
    sso_env(monkeypatch, CAPRI_ENABLE_SSO="true")
    assert sso_service.sso_config() is None


def test_config_is_complete_when_every_value_is_present(monkeypatch):
    sso_env(monkeypatch)
    cfg = sso_service.sso_config()
    assert cfg["tenant"] == "tenant-guid"
    assert cfg["client_id"] == "client-guid"
    assert cfg["client_secret"] == "shh"
    assert cfg["redirect_uri"] == "http://localhost:5100/api/auth/sso/callback"
    # Comma-separated object IDs become a set for the gate-2 intersection.
    assert cfg["groups"] == {"group-a", "group-b"}


@pytest.mark.parametrize("missing", [
    "CAPRI_SSO_TENANT_ID",
    "CAPRI_SSO_CLIENT_ID",
    "CAPRI_SSO_CLIENT_SECRET",
    "CAPRI_SSO_ALLOWED_GROUPS",
    "CAPRI_SSO_REDIRECT_URI",
])
def test_config_fails_closed_when_any_value_is_missing(monkeypatch, missing):
    # Fail closed on configuration: an incomplete config behaves as SSO-off so
    # a deployment typo cannot lock every user out of a working app.
    sso_env(monkeypatch, **{missing: None})
    assert sso_service.sso_config() is None


def test_config_fails_closed_on_a_blank_group_list(monkeypatch):
    # An empty group list would make gate 2 intersect against nothing.
    sso_env(monkeypatch, CAPRI_SSO_ALLOWED_GROUPS=" , ")
    assert sso_service.sso_config() is None


def test_error_codes_are_the_agreed_vocabulary():
    assert set(sso_service.ERROR_CODES) == {
        "no_groups_claim", "not_in_group", "unknown_user",
        "inactive_user", "identity_mismatch", "auth_failed",
    }


def test_sso_error_rejects_an_unknown_code():
    with pytest.raises(AssertionError):
        sso_service.SsoError("made_up_code")


def test_sso_error_keeps_detail_off_the_code():
    err = sso_service.SsoError("auth_failed", "tenant said no")
    assert err.code == "auth_failed"
    assert "tenant said no" in str(err)


@pytest.mark.parametrize("value", [
    "/requests/42",
    "/a/b?c=d",
    "/",
])
def test_safe_next_path_accepts_same_origin_paths(value):
    assert sso_service.safe_next_path(value) == value


@pytest.mark.parametrize("value", [
    "//evil.com",              # protocol-relative: another host entirely
    "https://evil.com",        # absolute
    "http://evil.com",
    "/ok\\evil",               # some browsers normalise the backslash to /
    "/ok\revil",               # header injection
    "/ok\nevil",
    "requests/42",             # not absolute
    "",
    None,
])
def test_safe_next_path_rejects_everything_else(value):
    # /sso/login is reachable before anyone signs in, so an unchecked next=
    # would make our own login endpoint an open redirect -- a phishing link
    # that genuinely starts at our hostname.
    assert sso_service.safe_next_path(value) == ""


# ------------------------------------------------------------- the MSAL seam

class FakeMsalApp:
    """Stands in for msal.ConfidentialClientApplication.

    Monkeypatching sso_service._client to return one of these is the only fake
    in the SSO tests -- everything else runs for real. We are testing our
    gates, not Microsoft's protocol.
    """

    def __init__(self, flow=None, result=None, raises=None):
        self._flow = flow if flow is not None else {
            "auth_uri": "https://login.microsoftonline.com/tenant-guid/authorize?x=1",
            "state": "st",
        }
        self._result = result
        self._raises = raises
        self.initiate_calls = []
        self.acquire_calls = []

    def initiate_auth_code_flow(self, scopes, redirect_uri=None):
        self.initiate_calls.append((scopes, redirect_uri))
        if self._raises:
            raise self._raises
        return self._flow

    def acquire_token_by_auth_code_flow(self, flow, args):
        self.acquire_calls.append((flow, args))
        if self._raises:
            raise self._raises
        return self._result


def use_fake(monkeypatch, fake):
    monkeypatch.setattr(sso_service, "_client", lambda cfg: fake)
    return fake


def test_build_auth_flow_asks_for_no_scopes(monkeypatch):
    sso_env(monkeypatch)
    fake = use_fake(monkeypatch, FakeMsalApp())
    flow = sso_service.build_auth_flow(sso_service.sso_config())
    assert flow["auth_uri"].startswith("https://login.microsoftonline.com/")
    scopes, redirect_uri = fake.initiate_calls[0]
    # No Graph scope: CAPRI acts on nothing on the user's behalf, so an access
    # token would be one nothing uses and something that can leak.
    assert scopes == []
    assert redirect_uri == "http://localhost:5100/api/auth/sso/callback"


def test_redeem_returns_id_token_claims(monkeypatch):
    sso_env(monkeypatch)
    claims = {"preferred_username": "A@X.com", "groups": ["group-a"], "oid": "oid-1"}
    use_fake(monkeypatch, FakeMsalApp(result={"id_token_claims": claims}))
    assert sso_service.redeem(
        sso_service.sso_config(), {"state": "st"}, {"code": "c"}) == claims


def test_redeem_collapses_an_msal_exception_to_auth_failed(monkeypatch):
    # MSAL raises a bare ValueError for a mismatched or absent state -- the
    # replay case this flow exists to catch -- and the same call also does
    # network I/O, which fails in its own ways. Every failure means the same
    # thing to a user, so it collapses to one code.
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp(raises=ValueError("state mismatch")))
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.redeem(sso_service.sso_config(), {"state": "st"}, {"code": "c"})
    assert exc.value.code == "auth_failed"


def test_redeem_treats_an_error_result_as_auth_failed(monkeypatch):
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp(result={
        "error": "invalid_grant",
        "error_description": "AADSTS70008: expired",
    }))
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.redeem(sso_service.sso_config(), {"state": "st"}, {"code": "c"})
    assert exc.value.code == "auth_failed"
    # The description can quote back attacker-influenced input, so it is logged
    # via the detail, never returned to the browser.
    assert "AADSTS70008" in str(exc.value)


def test_redeem_rejects_a_result_with_no_claims(monkeypatch):
    sso_env(monkeypatch)
    use_fake(monkeypatch, FakeMsalApp(result={"access_token": "no claims here"}))
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.redeem(sso_service.sso_config(), {"state": "st"}, {"code": "c"})
    assert exc.value.code == "auth_failed"


# ---------------------------------------------------------------- the gates

def _sso_user(email="a@x.com", active=True, entra_oid=None):
    from app.extensions import db
    from app.models import User
    from app.services.security import hash_password

    u = User(email=email, name="A User", password_hash=hash_password("secret123"),
             roles='["REQUESTOR"]', active=active, entra_oid=entra_oid)
    db.session.add(u)
    db.session.commit()
    return u


def _claims(**over):
    c = {"preferred_username": "a@x.com", "groups": ["group-a"], "oid": "oid-1"}
    c.update(over)
    return c


def _cfg(monkeypatch):
    sso_env(monkeypatch)
    return sso_service.sso_config()


def test_gate1_absent_groups_claim_is_not_membership_of_nothing(app, monkeypatch):
    # Entra omits `groups` entirely and emits _claim_names once a user is in
    # enough groups, so an absent claim is indistinguishable from an empty one.
    # Treating it as a pass would silently disable this gate for exactly the
    # accounts most likely to be over-privileged. IT fixes this.
    _sso_user()
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.resolve_user(_cfg(monkeypatch), _claims(groups=None))
    assert exc.value.code == "no_groups_claim"


def test_gate1_rejects_a_non_list_groups_claim(app, monkeypatch):
    _sso_user()
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.resolve_user(_cfg(monkeypatch), _claims(groups="group-a"))
    assert exc.value.code == "no_groups_claim"


def test_gate2_rejects_a_non_member(app, monkeypatch):
    _sso_user()
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.resolve_user(_cfg(monkeypatch), _claims(groups=["some-other-group"]))
    assert exc.value.code == "not_in_group"


def test_gate2_accepts_membership_of_any_one_allowed_group(app, monkeypatch):
    u = _sso_user()
    got = sso_service.resolve_user(_cfg(monkeypatch), _claims(groups=["group-b"]))
    assert got.id == u.id


def test_gate3_rejects_an_unknown_email(app, monkeypatch):
    # Deliberately not auto-provisioned: a row is an admin's decision.
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.resolve_user(_cfg(monkeypatch),
                                 _claims(preferred_username="nobody@x.com"))
    assert exc.value.code == "unknown_user"


def test_gate3_rejects_an_inactive_user(app, monkeypatch):
    _sso_user(active=False)
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.resolve_user(_cfg(monkeypatch), _claims())
    assert exc.value.code == "inactive_user"


def test_gate3_lowercases_the_email(app, monkeypatch):
    u = _sso_user(email="a@x.com")
    got = sso_service.resolve_user(_cfg(monkeypatch),
                                   _claims(preferred_username="A@X.COM"))
    assert got.id == u.id


def test_gate3_falls_back_to_the_email_claim(app, monkeypatch):
    # Which of preferred_username/email Entra populates depends on how the
    # account was created, so reading only the first refuses a real subset of
    # accounts as unknown.
    u = _sso_user()
    got = sso_service.resolve_user(
        _cfg(monkeypatch), _claims(preferred_username=None, email="a@x.com"))
    assert got.id == u.id


def test_gate4_pins_entra_oid_on_first_sight(app, monkeypatch):
    from app.extensions import db

    u = _sso_user(entra_oid=None)
    sso_service.resolve_user(_cfg(monkeypatch), _claims(oid="oid-1"))
    db.session.refresh(u)
    assert u.entra_oid == "oid-1"


def test_gate4_accepts_a_matching_oid(app, monkeypatch):
    u = _sso_user(entra_oid="oid-1")
    got = sso_service.resolve_user(_cfg(monkeypatch), _claims(oid="oid-1"))
    assert got.id == u.id


def test_gate4_refuses_a_different_oid_for_the_same_email(app, monkeypatch):
    # The email matched but the person did not. Refuse rather than hand over a
    # role, a division scope and authorship of approval-history rows.
    _sso_user(entra_oid="oid-1")
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.resolve_user(_cfg(monkeypatch), _claims(oid="oid-2"))
    assert exc.value.code == "identity_mismatch"


def test_gates_run_in_order_so_each_code_names_its_own_fixer(app, monkeypatch):
    # An inactive user who is also not in the group must report the GROUP
    # problem (IT) rather than the account problem (app admin): running the
    # gates out of order hands an IT problem to the wrong person.
    _sso_user(active=False)
    with pytest.raises(sso_service.SsoError) as exc:
        sso_service.resolve_user(_cfg(monkeypatch), _claims(groups=["nope"]))
    assert exc.value.code == "not_in_group"
