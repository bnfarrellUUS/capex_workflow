# Entra ID SSO — Implementation Guide for D&H United Flask Apps

**Date:** 2026-09-18 · **Author:** Bryan Farrell · **Status:** reference
**Reference implementation:** ARIA (`ar_dashboard`) — `server.py`, auth section

A recipe for adding Microsoft Entra ID single sign-on to one of our internal
Flask applications (SCORE/`bid_app`, CAPRI/`capex_tracking`, `messaging_app_nw`,
and whatever comes next), built from what ARIA actually shipped and what it cost
to get there.

The code is mechanical — MSAL does the protocol work in about 80 lines. The
decisions in section 2 and the traps in sections 4, 8 and 9 are what this
document is really for. Read those even if you copy the code without reading it.

---

## 1. What you are building

SSO replaces **authentication only**. Your app's roles, permissions, scoping and
session handling are untouched: at the end of a successful sign-in you call the
same `login_user()` you call today, and everything downstream cannot tell the
difference.

```
  Browser                    Your Flask app                  Entra ID
     |                             |                             |
     |-- GET /  ------------------>|                             |
     |<-- login screen ------------|                             |
     |-- GET /api/auth/config ---->|                             |
     |<-- {"sso_enabled": true} ---|                             |
     |                             |                             |
     | [ click "Sign in with Microsoft" ]                        |
     |-- GET /api/auth/sso/login ->|                             |
     |                             |- initiate_auth_code_flow    |
     |                             |  (state + PKCE -> session)  |
     |<-- 302 to Entra ------------|                             |
     |------------------------------ sign in --------------------->|
     |<----------------------------- 302 back with ?code= ---------|
     |-- GET /api/auth/sso/callback ->|                           |
     |                             |- acquire_token_by_auth_code_flow
     |                             |- GATE 1: groups claim present?
     |                             |- GATE 2: in an allowed group?
     |                             |- GATE 3: active row in users?
     |                             |- login_user()  <-- your existing session
     |<-- 302 to / (or ?next=) ----|                             |
```

This is the OAuth 2.0 authorization-code flow, server-side, with a confidential
client. Use **MSAL Python** (`msal.ConfidentialClientApplication`) — it generates
and validates `state`, does PKCE, and validates the ID token signature for you.
Do not hand-roll any of that.

**You only need the ID token.** Request no scopes beyond the OIDC defaults. The
app never calls Graph on the user's behalf, so there is no access token to store,
refresh or protect.

---

## 2. The five decisions

These transfer between apps; the code does not, quite. Each is ARIA's answer plus
the reason, because the reason is what tells you whether to copy it.

### 2.1 SSO-only, on a single switch

When SSO is configured, it is the **only** way in. `POST /api/auth/login` returns
**403** before touching the database or bcrypt, and the login screen renders only
the Microsoft button.

The switch is one condition — `_sso_config() is not None` — checked in both
places. Two independent flags ("SSO enabled" and "password login allowed") drift
apart and eventually leave a door open that nobody remembers.

> ARIA shipped hybrid first (2026-07-16) and moved to SSO-only two weeks later
> (PR #1467). A password form that still works is a password form that still gets
> phished, and it silently exempts anyone who keeps using it from MFA and
> conditional access. Section 10 keeps the hybrid state as a *staging* step, not
> an end state.

### 2.2 No password bypass — for anyone, including admins

There is no break-glass password path. It is tempting to leave one for the admin
account; do not. A bypass that exists for the admin is a bypass an attacker only
has to find once, and the admin account is the one worth taking.

**Recovery from a bad Entra state** is therefore operational, not in-app: set
`APP_ENABLE_SSO=0` and restart. Locally that is one line in `.env`; in a
container it is a pipeline redeploy. Write that down in your support runbook
*before* you turn SSO on, because the moment you need it is the moment nobody can
log in to look it up.

### 2.3 Group authenticates, local user row authorizes

Entra group membership is **necessary but not sufficient**. The signed-in email
must also match an **active** row in the app's own `users` table, and role,
permissions and any data scoping come from that row exactly as they do today.

- **No auto-provisioning.** An unknown email is rejected, not created.
- **No group→role mapping.** Roles live in the app, where the app's admin screen
  can see and change them.

Why: access to the app and authority inside the app are different questions with
different owners. IT owns the first (the security group); the business owner owns
the second (the users table). Mapping roles to groups moves every permission
change into an IT ticket, and auto-provisioning means a new hire in the group
gets an account in your app the day they join, whether or not anyone intended it.

The cost is that adding a user is two steps — group membership *and* a row in the
app — and the error messages in section 7.2 exist to make it obvious which step is
missing.

### 2.4 Fail closed on configuration, fail open on the flag

`_sso_config()` returns a config dict only when the flag is on **and every value
is present**. Any missing value makes it return `None`, which means SSO-off,
which means password login keeps working.

This is deliberately the *safe* failure, not the *secure* one. `APP_ENABLE_SSO=1`
with a half-filled config is a deployment mistake, and the alternative — refusing
all logins — locks every user out of a working app over a typo. The server logs a
startup `WARNING` so the mistake is visible rather than silent.

> ARIA's **dev** pipeline sets `AR_ENABLE_SSO=1` but ships **no** `AR_SSO_*`
> values, so dev runs on password login. That is this rule doing its job, not a
> broken deploy — see section 8.

### 2.5 Sessions are unchanged

SSO establishes the same Flask-Login session as before, with the same lifetime
and the same cookie. Record how they signed in (`session["auth_method"] = "sso"`)
and use it only for things that genuinely differ — ARIA suppresses the
forced-password-change prompt for SSO sessions, since there is no password to
change. Do not build a second session mechanism.

---

## 3. Prerequisites your app must already have

Before starting, confirm all four. If any is missing, fix it first — SSO on a
shaky auth foundation just moves the problem.

| # | Prerequisite | Why |
|---|---|---|
| 1 | A `users` table keyed on **work email**, with an active flag | Gate 3 looks the user up by the email Entra returns. Emails must match the tenant's, lowercased. |
| 2 | Server-side sessions with a stable secret key | The auth-code flow stores `state`/PKCE in the session between two requests. A secret key that changes on restart breaks every in-flight sign-in. |
| 3 | **One** place that decides who is signed in | Flask-Login's `login_user`/`current_user`. If authentication is scattered, consolidate before adding a second entry point to it. |
| 4 | An admin screen (or a documented SQL path) to add users | Adding a user becomes a prerequisite for that user signing in at all. |

Minimum users-table shape — ARIA's, reduced to what SSO touches:

```sql
CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE,   -- lowercased work email; the SSO join key
    name          TEXT NOT NULL,
    role          TEXT NOT NULL,          -- your app's roles; SSO does not set this
    is_active     INTEGER NOT NULL DEFAULT 1,
    password_hash TEXT,                   -- still needed during the hybrid window
    last_login    TEXT
);
```

Keep `password_hash` nullable and keep the column even after going SSO-only: it
is what makes `APP_ENABLE_SSO=0` an actual recovery lever rather than a way to
lock everyone out differently.

---

## 4. Entra app registration (the IT request)

**One app registration per application per tenant.** Do not share ARIA's — the
redirect URIs, the authorizing group and the secret rotation schedule are all
per-app, and sharing a registration means one app's secret rotation breaks the
others.

Send IT this list. Copy `docs/it-requests/2026-07-16-entra-sso-values.md` from
ARIA as the template and change the names.

| # | Item | Fills |
|---|---|---|
| 1 | Directory (tenant) ID | `APP_SSO_TENANT_ID` |
| 2 | Application (client) ID | `APP_SSO_CLIENT_ID` |
| 3 | Client secret — **via a secure channel, never email** | `APP_SSO_CLIENT_SECRET` |
| 4 | Object ID(s) of the authorizing security group(s) | `APP_SSO_ALLOWED_GROUPS` |
| 5 | The exact redirect URI(s) registered on the app | `APP_SSO_REDIRECT_URI` |

And confirm four things explicitly:

- [ ] **The `groups` claim is emitted in ID tokens.** Token configuration →
      *Groups assigned to the application*, with the authorizing group assigned
      to the app. Without this the app fails closed at Gate 1 for everyone and
      the symptom (`no_groups_claim`) looks like an app bug.
- [ ] **Redirect URIs are registered for every environment**, exactly — scheme,
      host, port, path, no trailing slash. Entra matches them literally.
- [ ] Intended users are in the authorizing group **and** have an active row in
      the app with the same work email.
- [ ] Someone owns the **client secret expiry date** and has a calendar reminder.
      An expired secret is a total outage with no in-app warning.

### 4.1 The redirect-URI trap

Entra permits plain `http://` **only for `localhost`**. Everything else must be
`https://`.

This blocked ARIA's production SSO for months: the container was reachable at
`http://172.16.12.132:5000`, which cannot be registered at all. A bare IP has no
certificate, and Entra will not take it.

**Plan for this before you write any code.** The deployed app needs a DNS name
and HTTPS — App Service, Front Door, an application gateway, whatever the pattern
is when you get there. Until it has one, that environment keeps
`APP_ENABLE_SSO=0` and runs on password login, which is exactly what the
fail-closed rule in 2.4 gives you for free.

Prefer *Groups assigned to the application* over *All groups* for the claim. With
all groups, a user in many groups overflows the claim and Entra sends a link to
fetch them instead of the list itself — the claim goes missing for exactly the
most-connected users, which is a memorably confusing bug.

---

## 5. Environment variables

Six variables, one prefix. Use your app's prefix (`CAPRI_`, `SCORE_`); `APP_`
below is the placeholder.

| Variable | Purpose |
|---|---|
| `APP_ENABLE_SSO` | `1` turns SSO on and makes it the only login method. Anything else, or an incomplete config, leaves password login as the only method. |
| `APP_SSO_TENANT_ID` | Directory (tenant) ID |
| `APP_SSO_CLIENT_ID` | Application (client) ID |
| `APP_SSO_CLIENT_SECRET` | Client secret — **secret**: Key Vault or `.env`, never git |
| `APP_SSO_ALLOWED_GROUPS` | Comma-separated group **object IDs**; membership in any one grants access |
| `APP_SSO_REDIRECT_URI` | The exact registered redirect URI for *this* environment |

Only the secret is a secret. Tenant, client ID, group IDs and redirect URI are
identifiers, not credentials — keeping them out of Key Vault makes the pipeline
simpler and leaks nothing.

Read them **at request time** from `os.environ`, not into module-level constants
at import. It costs nothing, and it is what lets the test suite flip the config
per test with `monkeypatch` (section 9).

---

## 6. Backend implementation

Adapted from `ar_dashboard/server.py:399-510`. Add `msal` to `requirements.txt`.

### 6.1 Config and the MSAL client

```python
import os
import msal
from flask import redirect, request, session, jsonify
from flask_login import login_user


def _sso_config():
    """Entra SSO settings from env, or None unless APP_ENABLE_SSO=1 and complete
    (fail closed: a partial configuration behaves as SSO-off).

    Not None also means SSO is the *only* way in: password sign-in is refused
    and the login screen hides the email/password form."""
    if os.environ.get("APP_ENABLE_SSO", "").strip() != "1":
        return None
    cfg = {
        "tenant": os.environ.get("APP_SSO_TENANT_ID", "").strip(),
        "client_id": os.environ.get("APP_SSO_CLIENT_ID", "").strip(),
        "client_secret": os.environ.get("APP_SSO_CLIENT_SECRET", "").strip(),
        "groups": {g.strip() for g in
                   os.environ.get("APP_SSO_ALLOWED_GROUPS", "").split(",") if g.strip()},
        "redirect_uri": os.environ.get("APP_SSO_REDIRECT_URI", "").strip(),
    }
    if not (cfg["tenant"] and cfg["client_id"] and cfg["client_secret"]
            and cfg["groups"] and cfg["redirect_uri"]):
        return None
    return cfg


def _msal_app(cfg):
    return msal.ConfidentialClientApplication(
        cfg["client_id"],
        client_credential=cfg["client_secret"],
        authority=f"https://login.microsoftonline.com/{cfg['tenant']}",
    )
```

`_sso_config() is not None` is the single switch from 2.1. Every other decision
in the app keys off it.

### 6.2 Telling the login screen which mode it is in

```python
@app.route("/api/auth/config", methods=["GET"])
def api_auth_config():
    """Unauthenticated: tells the login screen whether to offer SSO."""
    return jsonify({"ok": True, "sso_enabled": _sso_config() is not None})
```

This endpoint has to exist and has to be unauthenticated: `/api/auth/me` returns
401 before login, so the login screen has no other way to learn which form to
draw. It leaks one boolean, which is visible from the login page anyway.

### 6.3 The open-redirect guard

```python
def _safe_next_path(value) -> str:
    """A post-login landing path from an untrusted query string, or "".

    /api/auth/sso/login is reachable before anyone has signed in, so whatever it
    is handed has to be treated as hostile: only a path on this origin may come
    back out. A value starting "//" (or carrying a backslash, which some browsers
    normalise to "/") would redirect to another host entirely, turning our own
    login endpoint into an open redirect.
    """
    v = (value or "").strip()
    if not v.startswith("/") or v.startswith("//"):
        return ""
    if any(c in v for c in ("\\", "\r", "\n")):
        return ""
    return v
```

**Mandatory if you accept a `?next=` at all.** A pre-auth endpoint that redirects
wherever it is told is a phishing primitive on your own domain: the link
genuinely starts at your hostname, so it survives a careful look, and lands on an
attacker's login clone. Allow paths on this origin and nothing else.

If your app never deep-links from email, skip `?next=` entirely and always land
on `/`. Less surface, nothing lost.

### 6.4 The two routes

```python
@app.route("/api/auth/sso/login", methods=["GET"])
def api_auth_sso_login():
    cfg = _sso_config()
    if cfg is None:
        return _err("Not found", 404)
    try:
        flow = _msal_app(cfg).initiate_auth_code_flow(
            scopes=[], redirect_uri=cfg["redirect_uri"])
    except Exception:
        return redirect("/?sso_error=auth_failed")
    session["sso_flow"] = flow
    session["sso_next"] = _safe_next_path(request.args.get("next"))
    return redirect(flow["auth_uri"])


@app.route("/api/auth/sso/callback", methods=["GET"])
def api_auth_sso_callback():
    cfg = _sso_config()
    if cfg is None:
        return _err("Not found", 404)
    flow = session.pop("sso_flow", None)
    nxt = session.pop("sso_next", "") or "/"
    if not flow:
        return redirect("/?sso_error=auth_failed")
    try:
        result = _msal_app(cfg).acquire_token_by_auth_code_flow(
            flow, request.args.to_dict())
    except Exception:
        return redirect("/?sso_error=auth_failed")
    claims = result.get("id_token_claims")
    if not claims:
        return redirect("/?sso_error=auth_failed")

    # GATE 1 - claim present at all (not configured, overage, or no groups)
    groups = claims.get("groups")
    if groups is None:
        return redirect("/?sso_error=no_groups_claim")
    # GATE 2 - member of an authorizing group
    if not cfg["groups"] & set(groups):
        return redirect("/?sso_error=not_in_group")
    # GATE 3 - known, active user in this app
    email = (claims.get("preferred_username") or claims.get("email") or "").strip().lower()
    row = _get_db().get_user_by_email(email) if email else None
    if not row:
        return redirect("/?sso_error=unknown_user")
    if not row["is_active"]:
        return redirect("/?sso_error=inactive_user")

    user = User(row)
    session.permanent = True
    login_user(user, remember=False)
    session["auth_method"] = "sso"
    _get_db().update_last_login(user.id)
    return redirect(nxt)
```

Points worth keeping when you adapt it:

- **Both routes 404 when SSO is off.** Endpoints that exist only in one mode
  should not answer in the other.
- **`session.pop`, not `session.get`.** A flow is single-use; leaving it in the
  session invites replay.
- **A missing flow fails closed.** Someone hitting `/callback` directly, or after
  the session expired, gets `auth_failed` — never a partial sign-in.
- **Gates run in order, each with its own error code.** One generic "access
  denied" would make section 11 impossible to act on.
- **`groups is None` is distinct from an empty match.** `None` means the claim
  never arrived (an IT configuration problem); an empty intersection means the
  user is genuinely not in the group (an access-request problem). Different
  people fix them.
- **Email is lowercased** before the lookup, and read from `preferred_username`
  with `email` as fallback — which of the two Entra populates depends on how the
  account was created.
- **Every failure is a redirect to the login screen**, never a JSON error. The
  browser is doing a top-level navigation here; a JSON body renders as a blank
  white page with text on it.

### 6.5 Closing the password door

```python
@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    if _sso_config() is not None:
        return _err("Password sign-in is disabled. Use Sign in with Microsoft.", 403)
    ...  # existing bcrypt path, unchanged
```

First line of the handler — **before** reading the body, touching the database or
hashing anything. It is cheap, it cannot be reached around, and it means a
credential-stuffing run against an SSO-only app costs you one string comparison
per request instead of a bcrypt.

---

## 7. Frontend login screen

Three things, all in the login component.

### 7.1 Tri-state, not boolean

```jsx
/* null until /api/auth/config answers: SSO-on means SSO *only*, so rendering the
   password form before we know would flash a form that then disappears. */
const [ssoEnabled, setSsoEnabled] = useState(null);

useEffect(() => {
  apiFetch('/api/auth/config')
    .then(r => setSsoEnabled(!!r.sso_enabled))
    .catch(() => setSsoEnabled(false));
}, []);

...
{ssoEnabled === null  && <div>Loading sign-in options…</div>}
{ssoEnabled === true  && <button onClick={() => { window.location = ssoLoginUrl(); }}>
                            Sign in with Microsoft</button>}
{ssoEnabled === false && <form onSubmit={handleSubmit}>…</form>}
```

Defaulting to `false` makes every page load flash a password form that vanishes a
moment later — which reads as a broken app and trains users to type credentials
into a form that is about to disappear.

`catch → false` is the right fallback: if the config call fails, the server is
probably down, and the password form at least produces a comprehensible error.

### 7.2 Error codes → human sentences

The server redirects to `/?sso_error=<code>`. Translate on the client, show the
message, then **strip the parameter** so a refresh does not resurrect a stale
error.

```jsx
const params = new URLSearchParams(window.location.search);
const code = params.get('sso_error');
if (code) {
  const msgs = {
    not_in_group:    "Your Microsoft account isn't in the authorized security group. Contact IT to request access.",
    no_groups_claim: "Microsoft sign-in succeeded but no group information was returned. Contact IT.",
    unknown_user:    "Your Microsoft account isn't set up in this app yet. Ask an admin to add your user.",
    inactive_user:   "Your account is deactivated. Contact an admin.",
    auth_failed:     "Microsoft sign-in failed or was cancelled. Please try again.",
  };
  setError(msgs[code] || 'Microsoft sign-in failed.');
  params.delete('sso_error');
  const qs = params.toString();
  window.history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
}
```

Each message names **who fixes it** — IT for the first two, an app admin for the
next two, the user for the last. That single detail removes most of the support
traffic this feature would otherwise generate.

### 7.3 Carrying a deep link through the round trip

Only if your app links into itself from email or chat.

```jsx
const ssoLoginUrl = () => API_BASE + '/api/auth/sso/login?next=' +
  encodeURIComponent(window.location.pathname + window.location.search);
```

The callback redirects to a bare `/`, so without this an emailed deep link is
silently thrown away at sign-in and the reader lands on the home screen wondering
what the link was for. ARIA hit this with its unread-ping digest; the server side
is `_safe_next_path` plus `session["sso_next"]` in 6.3–6.4.

---

## 8. Deployment

### 8.1 Where the values live

| Value | Where |
|---|---|
| `APP_ENABLE_SSO`, tenant ID, client ID, group IDs, redirect URI | Plain environment variables in the pipeline's container env block |
| `APP_SSO_CLIENT_SECRET` | **Key Vault**, fetched at deploy time into a secure env var |

Per environment, always. Dev and prod are separate app registrations, separate
Key Vaults and separate redirect URIs. Nothing is shared but the tenant.

### 8.2 The Key Vault rule

The pipeline reads Key Vault at **deploy** time and bakes the values into the
container's environment. **Updating a secret does nothing until that
environment's pipeline runs again.** A rotated client secret has to land in the
dev vault *and* the prod vault, each followed by its own deploy — otherwise the
app works in dev and is dead in prod, with an error that points at Entra rather
than at the deploy you did not run.

### 8.3 Validate secrets before the container swaps

An empty Key Vault fetch is silent: the pipeline succeeds, the container comes up
with a blank secret, `_sso_config()` fails closed, and SSO is mysteriously off.
ARIA's prod pipeline guards against it (`pipelines/AppPipelineProd.yml:115-132`):

```bash
MISSING=()
[ -z "${APP_SSO_CLIENT_ID:-}" ]     && MISSING+=("entra-client-id")
[ -z "${APP_SSO_CLIENT_SECRET:-}" ] && MISSING+=("entra-client-secret")
[ -z "${APP_SSO_TENANT_ID:-}" ]     && MISSING+=("entra-tenant-id")
[ -z "${APP_SSO_REDIRECT_URI:-}" ]  && MISSING+=("entra-redirect-uri")
if [ ${#MISSING[@]} -gt 0 ]; then
  echo "##vso[task.logissue type=error]Missing secrets from Key Vault: ${MISSING[*]}"
  exit 1
fi
```

Fail the deploy loudly instead of shipping a quietly broken config.

### 8.4 Environments can differ, on purpose

ARIA's dev pipeline sets `AR_ENABLE_SSO=1` and supplies **no** `AR_SSO_*` values,
so dev fails closed to password login while prod runs SSO-only with the full set.
That is intentional — developers keep a fast local-style login, production keeps
the real gate — and it is only safe because of 2.4. Copy the pattern if it suits
you, but **write down** which environment is in which mode, or the next person
will report dev as a broken deploy.

---

## 9. Testing

### 9.1 The trap that will cost you an afternoon

If the app loads `.env` at import (and it does, if it uses `load_dotenv()`), a
developer whose `.env` has `APP_ENABLE_SSO=1` makes **every password-login test
in the suite** 403. Worse, it moves: the failure depends on which test imports
the app module first, so it passes alone and fails in the suite, or vice versa.

Clear the SSO variables for all tests and let the SSO tests opt back in
(`tests/conftest.py`):

```python
# Import the app module here, once, purely for the side effect: it calls
# load_dotenv(), which puts the .env values back into os.environ. A test that is
# the first to import it therefore re-acquired APP_ENABLE_SSO=1 *after* the
# fixture below had cleared it, and 403'd on login while every later test in the
# session passed — a failure that moved around as tests were added.
import server  # noqa: E402,F401

SSO_ENV_VARS = ("APP_ENABLE_SSO", "APP_SSO_TENANT_ID", "APP_SSO_CLIENT_ID",
                "APP_SSO_CLIENT_SECRET", "APP_SSO_ALLOWED_GROUPS",
                "APP_SSO_REDIRECT_URI")


@pytest.fixture(autouse=True)
def _no_ambient_sso():
    saved = {k: os.environ.pop(k, None) for k in SSO_ENV_VARS}
    yield
    for k, v in saved.items():
        if v is not None:
            os.environ[k] = v
```

The `import server` above the fixture is load-bearing. Do not tidy it away.

### 9.2 What to cover

Fake the MSAL calls — monkeypatch `_msal_app` to return a stub whose
`acquire_token_by_auth_code_flow` yields the `id_token_claims` each case needs.
You are testing your gates, not Microsoft's protocol. ARIA's `tests/test_sso.py`
is 16 tests; these are the ones worth having:

| Test | Asserts |
|---|---|
| Config requires flag **and** every value | Each variable removed in turn yields `None` |
| `/api/auth/config` | Reports true/false matching the config |
| `/sso/login` redirects and stores the flow | 302 to Entra, flow in session |
| `/sso/login` on MSAL error | Redirects to the login screen, not a 500 |
| Both routes 404 when SSO off | No half-live endpoints |
| Callback success | Session established, `auth_method == "sso"` |
| Callback rejections | One case per gate → the right `sso_error` code |
| Inactive user | `inactive_user`, no session |
| Callback with no flow in session | Fails closed |
| Password login refused when SSO on | **403** |
| Password login survives incomplete config | Fail-closed rule (2.4) |
| `_safe_next_path` | Accepts `/a/b?c=d`; rejects `//evil.com`, `https://evil.com`, backslashes, CR/LF |
| Deep link survives the round trip | `?next=` in → that path out |
| Off-site `next` discarded | Lands on `/`, not the attacker |

The `_safe_next_path` cases are pure-function tests and cost nothing. Write them.

### 9.3 Manual check before enabling

Nothing above proves the Entra side. Once IT delivers the values, verify by hand
in the target environment: a member of the group with an app row signs in; a
member **without** an app row sees `unknown_user`; a non-member sees
`not_in_group`; and a deactivated user sees `inactive_user`.

---

## 10. Rollout sequence

Four steps. Do not skip to 3.

**Step 0 — Build with the flag off.** Ship all the code with `APP_ENABLE_SSO`
unset. Nothing changes for users; the SSO routes 404. Merge and deploy normally,
so the code is in production and proven harmless before it is live.
*Go/no-go:* password login still works everywhere; SSO tests pass.

**Step 1 — Request the Entra registration.** Section 4. Expect this to take
longer than the code did, and expect the redirect-URI/HTTPS question (4.1) to be
the long pole. Nothing blocks on it — step 0 is already deployed.
*Go/no-go:* all five values in hand, `groups` claim confirmed, HTTPS redirect
registered for the target environment.

**Step 2 — Hybrid, in a lower environment only.** Temporarily allow both methods
(skip the 403 in 6.5), turn the flag on in dev, and have a handful of real users
sign in with Microsoft. This is where you find the claim misconfigurations and
the email mismatches, with a working password form still underneath.
*Go/no-go:* every pilot user signs in via SSO; every rejection shows the right
message; the users table matches the group.

**Step 3 — SSO-only.** Restore the 403, enable the flag in the target
environment, and announce it. Make sure the support runbook already contains the
`APP_ENABLE_SSO=0` recovery from 2.2.
*Go/no-go:* all users have both group membership and an active row, and someone
other than you can perform the recovery.

Keep step 2 short and confined to a lower environment. A hybrid production app is
the configuration 2.1 exists to avoid.

---

## 11. Failure modes

| Symptom / code | Actual cause | Who fixes it |
|---|---|---|
| `no_groups_claim` | Token configuration does not emit `groups`, **or** the user is in so many groups the claim overflowed (use *Groups assigned to the application*), **or** the user is in no groups at all | IT |
| `not_in_group` | Signed in fine, not a member of an authorizing group — or `APP_SSO_ALLOWED_GROUPS` has the wrong object ID | IT (access request) |
| `unknown_user` | No row in the app's users table for that email, or the email differs from the Entra one | App admin |
| `inactive_user` | Row exists but is deactivated | App admin |
| `auth_failed` | Cancelled at the Microsoft screen, expired session, replayed callback, or an MSAL error — commonly a **redirect URI mismatch** or an **expired client secret** | User (retry), then IT |
| SSO button never appears | `_sso_config()` returned `None` — a missing variable. Check the startup WARNING | Deployer |
| Works in dev, dead in prod | Secret set in one Key Vault only, or set but not redeployed (8.2) | Deployer |
| Everyone locked out | Entra outage, expired secret, or a bad config | Set `APP_ENABLE_SSO=0`, restart/redeploy (2.2) |
| Whole suite 403s on login | Developer `.env` leaking into tests (9.1) | Developer |
| Sign-in loops back to login | Session cookie not persisting — secret key changing on restart, or a proxy stripping the cookie | Developer |

---

## 12. Checklist

Copy into the implementing app's issue.

**Code**
- [ ] `msal` in `requirements.txt`
- [ ] `_sso_config()` — fail closed on any missing value
- [ ] `_msal_app()`
- [ ] `GET /api/auth/config` — unauthenticated
- [ ] `_safe_next_path()` (or no `?next=` at all)
- [ ] `GET /api/auth/sso/login` — 404 when off
- [ ] `GET /api/auth/sso/callback` — three gates, distinct error codes, 404 when off
- [ ] `POST /api/auth/login` — 403 as the first line when SSO is on
- [ ] `session["auth_method"]`, and any password-specific prompt suppressed for SSO
- [ ] Startup WARNING when the flag is on but the config is incomplete

**Frontend**
- [ ] Tri-state `ssoEnabled` (null / true / false)
- [ ] Microsoft button; password form only when `false`
- [ ] `sso_error` code→message map, parameter stripped from the URL after display
- [ ] `?next=` carried into `/sso/login` (if deep-linking)

**Entra**
- [ ] Own app registration, per app
- [ ] `groups` claim via *Groups assigned to the application*
- [ ] Redirect URIs registered per environment, HTTPS outside localhost
- [ ] Client secret delivered securely; expiry date owned and diarised

**Deployment**
- [ ] Secret in **every** environment's Key Vault
- [ ] Pipeline env block per environment; secret as a secure env var
- [ ] Pre-flight secret validation that fails the deploy
- [ ] Which environment is in which mode, written down

**Tests**
- [ ] `conftest.py` clears the SSO vars (with the load-bearing import above it)
- [ ] The table in 9.2
- [ ] Manual four-user check in the target environment

**Operations**
- [ ] Support runbook: the `APP_ENABLE_SSO=0` recovery
- [ ] Support runbook: the failure-mode table from section 11
- [ ] Documented how a new user is granted access (group **and** app row)

---

## References

Everything here has a working counterpart in `ar_dashboard`:

| Topic | Where |
|---|---|
| Backend | `server.py:399-510` (SSO section), `server.py:320-321` (the 403) |
| Login screen | `AR_Dashboard.html`, `LoginScreen` component |
| Tests | `tests/test_sso.py`, `tests/conftest.py` |
| Pipelines | `pipelines/AppPipeline.yml` (dev, fails closed), `pipelines/AppPipelineProd.yml:83-197` (prod, full config + pre-flight) |
| IT request template | `docs/it-requests/2026-07-16-entra-sso-values.md` |
| Original designs | `docs/superpowers/specs/2026-07-16-entra-sso-design.md`, `docs/superpowers/specs/2026-07-29-sso-only-login-design.md` |
| Microsoft | [MSAL Python docs](https://learn.microsoft.com/entra/msal/python/), [Flask web app tutorial](https://learn.microsoft.com/entra/identity-platform/tutorial-web-app-python-sign-in-users) |
