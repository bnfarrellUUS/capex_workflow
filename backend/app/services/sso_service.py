"""Entra ID SSO -- spec docs/superpowers/specs/2026-09-21-capri-entra-sso-design.md.

The ONLY module in CAPRI that imports msal. Everything above it deals in claim
dicts and User rows, which is what makes the callback's six refusal codes
testable without a network.

WHAT THIS MODULE DELIBERATELY DOES NOT DO:
  - It never validates a token by hand. acquire_token_by_auth_code_flow checks
    the signature against the tenant's JWKS, the issuer, the audience, the
    nonce and the state. Reimplementing any of that is how signature checks get
    accidentally disabled.
  - It keeps no token cache and retains no token. CAPRI acts on nothing on a
    user's behalf, so everything except id_token_claims is discarded the moment
    the claims are read, and only the Flask-Login session survives.

    Note it does not follow that no refresh token is ISSUED. MSAL decorates
    whatever scopes you pass with `openid profile offline_access`, so the
    authorize request carries offline_access however empty SCOPES is -- checked
    against the live tenant on 2026-09-21. There is no supported way to
    suppress it through initiate_auth_code_flow. Nothing here reads or stores
    the refresh token, so it dies with the response object; the point of
    recording this is that "we never asked for one" would be untrue.
"""
import os

import msal

from app.extensions import db
from app.models import User

# The complete set of refusal codes. They reach the browser in a query string,
# so they are a fixed server-side vocabulary and never interpolated text: no
# exception message, claim value or email address may leak this way.
ERROR_CODES = (
    "no_groups_claim",
    "not_in_group",
    "unknown_user",
    "inactive_user",
    "identity_mismatch",
    "auth_failed",
)

# Only the OIDC basics. CAPRI calls no downstream API on the user's behalf, so
# a Graph scope would obtain an access token nothing uses -- and a token
# obtained is a token that can leak. Empty is as small as this gets: MSAL adds
# `openid profile offline_access` itself (see the module docstring).
SCOPES = []


class SsoError(Exception):
    """A refusal carrying a code from ERROR_CODES."""

    def __init__(self, code, detail=""):
        assert code in ERROR_CODES, f"unknown SSO error code {code!r}"
        super().__init__(detail or code)
        self.code = code


def sso_config():
    """Entra settings from the environment, or None.

    None means SSO is off. Not-None means SSO is the *only* way in: password
    sign-in is refused and the login screen hides the email/password form. One
    condition, checked in both places -- two independent flags drift apart and
    eventually leave a door open nobody remembers.

    Fail closed on configuration: any missing value yields None, i.e. SSO-off,
    i.e. password login keeps working. That is deliberately the *safe* failure
    rather than the *secure* one -- an incomplete config is a deployment
    mistake, and refusing every login over a typo is worse. create_app logs a
    WARNING so the mistake is visible rather than silent.

    Read from os.environ at CALL time, never into module-level constants at
    import: it costs nothing, and it is what lets the suite flip the config per
    test with monkeypatch. app/config.py's import-time pattern must not be
    copied here.
    """
    if os.environ.get("CAPRI_ENABLE_SSO", "").strip() != "1":
        return None
    cfg = {
        "tenant": os.environ.get("CAPRI_SSO_TENANT_ID", "").strip(),
        "client_id": os.environ.get("CAPRI_SSO_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("CAPRI_SSO_CLIENT_SECRET", "").strip(),
        "groups": {g.strip() for g
                   in os.environ.get("CAPRI_SSO_ALLOWED_GROUPS", "").split(",")
                   if g.strip()},
        "redirect_uri": os.environ.get("CAPRI_SSO_REDIRECT_URI", "").strip(),
    }
    if not all((cfg["tenant"], cfg["client_id"], cfg["client_secret"],
                cfg["groups"], cfg["redirect_uri"])):
        return None
    return cfg


def safe_next_path(value):
    """A post-login landing path from an untrusted query string, or "".

    /api/auth/sso/login is reachable before anyone has signed in, so whatever
    it is handed has to be treated as hostile: only a path on this origin may
    come back out. A value starting "//" -- or carrying a backslash, which some
    browsers normalise to "/" -- would redirect to another host entirely,
    turning our own login endpoint into an open redirect. The link genuinely
    starts at our hostname, so it survives a careful look and lands on a login
    clone.
    """
    v = (value or "").strip()
    if not v.startswith("/") or v.startswith("//"):
        return ""
    if any(c in v for c in ("\\", "\r", "\n")):
        return ""
    return v


def _client(cfg):
    """A HOOK, and the one seam the tests fake.

    Everything else in this module and in blueprints/auth.py is exercised for
    real; monkeypatching this is what keeps the suite off the network.
    """
    return msal.ConfidentialClientApplication(
        cfg["client_id"],
        authority=f"https://login.microsoftonline.com/{cfg['tenant']}",
        client_credential=cfg["client_secret"],
    )


def build_auth_flow(cfg):
    """The flow dict carrying state, nonce and the PKCE code_verifier.

    The caller stores this in the Flask session and MUST pop it on the way
    back: a flow read in place rather than popped makes a replayed callback URL
    usable a second time.

    response_mode is left at MSAL's default (query, i.e. a GET redirect) and
    MUST NOT be changed to form_post -- including when MSAL itself emits
    `UserWarning: response_mode='form_post' is recommended for better
    security` on every call, which it does. app/config.py sets
    SESSION_COOKIE_SAMESITE="Lax", which does not send the cookie on a
    cross-site POST -- so a form_post callback would arrive with no session,
    the flow dict would be unreachable, and every sign-in would fail while
    looking exactly like an Entra misconfiguration.
    """
    return _client(cfg).initiate_auth_code_flow(
        SCOPES, redirect_uri=cfg["redirect_uri"])


def redeem(cfg, flow, args):
    """Exchange the code for validated ID token claims.

    `args` is request.args; MSAL reads `code` and `state` from it and compares
    the state against the flow dict. A mismatched or absent state -- the
    CSRF/replay case this flow exists to catch -- does NOT come back as an
    error dict: MSAL raises a bare ValueError, which is why the call below is
    wrapped rather than trusted to always return.
    """
    try:
        result = _client(cfg).acquire_token_by_auth_code_flow(flow, dict(args))
    except Exception as e:
        # Deliberately broad, not `except ValueError`. MSAL documents
        # client-side data errors as ValueError, but this call also does
        # network I/O, which fails in its own ways. Every failure means the
        # same thing to a user -- sign-in did not complete -- so it collapses
        # to one code rather than leaking which exception type fired.
        raise SsoError("auth_failed", f"exception during token exchange: {e}") from e
    if "error" in result or "id_token_claims" not in result:
        # The description can quote back attacker-influenced input, so it goes
        # in the detail (logged) and never in the code (returned).
        raise SsoError(
            "auth_failed",
            str(result.get("error_description") or result.get("error")))
    return result["id_token_claims"]


def resolve_user(cfg, claims):
    """Claims -> the User row that may sign in, or SsoError.

    Entra proves WHO. This function is the whole of what decides WHETHER, and
    the User row an admin created decides everything after: roles, division,
    delegate and approval routing are untouched by SSO.

    FOUR GATES, IN THIS ORDER, and the order is the guide's rather than the
    obvious one. Each gate's code names a different person to act on it, so
    running them out of order would hand an IT problem to an app admin.
    """
    # GATE 1 -- did the claim arrive at all?
    #
    # `None` is NOT "member of nothing". Entra omits `groups` entirely and
    # emits `_claim_names` instead once a user is in enough groups, so an
    # absent claim is indistinguishable from an empty one -- and treating it as
    # a pass would silently disable this gate for exactly the accounts most
    # likely to be over-privileged. IT fixes this, by setting Token
    # configuration to "Groups assigned to the application".
    groups = claims.get("groups")
    if not isinstance(groups, list):
        raise SsoError("no_groups_claim")

    # GATE 2 -- is this user in an authorizing group? An access request, not a
    # configuration bug. cfg["groups"] is never empty: sso_config() treats a
    # blank group list as unconfigured.
    if not set(groups) & cfg["groups"]:
        raise SsoError("not_in_group")

    # GATE 3 -- is there an active row an admin created?
    #
    # `email` is a fallback for `preferred_username`, not a nicety: which of
    # the two Entra populates depends on how the account was created, so
    # reading only the first refuses a real subset of accounts as unknown.
    email = (claims.get("preferred_username")
             or claims.get("email") or "").strip().lower()
    user = (db.session.query(User).filter_by(email=email).one_or_none()
            if email else None)
    if user is None:
        # Deliberately not auto-provisioned. A row is an admin's decision, and
        # access to the app is a different question from authority inside it.
        raise SsoError("unknown_user")
    if not user.active:
        raise SsoError("inactive_user")

    # GATE 4 -- is it the same person the row was pinned to?
    oid = (claims.get("oid") or "").strip()
    if user.entra_oid and user.entra_oid != oid:
        # The email matched but the person did not.
        raise SsoError("identity_mismatch")
    if not user.entra_oid and oid:
        user.entra_oid = oid
        db.session.commit()
    return user
