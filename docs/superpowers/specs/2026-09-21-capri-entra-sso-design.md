# CAPRI — Entra ID SSO design

**Date:** 2026-09-21 · **Status:** approved, not yet implemented
**Guide:** `docs/entra-sso-implementation-guide.md` (the D&H house recipe)
**Closest reference implementation:** APEX (`../apex`) — `backend/sso.py`,
`backend/api/auth.py`, `tests/test_sso.py`, built 2026-09-18 from the same guide.

This spec covers **Step 0 of the guide's §10 rollout only**: all the code, tests
and documentation, shipped with `CAPRI_ENABLE_SSO` unset. Nothing changes for any
user, the SSO routes 404, and the Entra app registration is not a blocker.
Steps 1–3 (the IT request, a hybrid pilot, SSO-only) come later.

---

## 1. What this changes, and what it deliberately does not

SSO replaces **authentication only**. At the end of a successful sign-in we call
the same `login_user()` the password path calls, so roles, approval routing,
delegates, worklists and every authz rule downstream cannot tell the difference.

Unchanged on purpose:

- `roles`, `division_id`, `delegate_id` and every `workflow_service` pool rule.
- The password endpoints, `ChangePasswordPage`, the profile password form and the
  admin password reset. They stay because they are what makes
  `CAPRI_ENABLE_SSO=0` a real recovery lever rather than a different way to lock
  everyone out (guide §2.2).
- `must_change_password` on the row. It is skipped for SSO sessions, not cleared,
  so it still bites if SSO is ever switched off.

## 2. The five house decisions, as they apply to CAPRI

Taken from guide §2. CAPRI's answer is the guide's answer in all five.

1. **SSO-only, on a single switch.** When `sso_config()` is not `None`, SSO is the
   only way in: `POST /api/auth/login` returns 403 and the login screen renders
   only the Microsoft button. One condition, checked in both places — two
   independent flags drift apart and leave a door open nobody remembers.
2. **No password bypass, including for admins.** Recovery from a bad Entra state
   is operational: `CAPRI_ENABLE_SSO=0` and restart. This must be in the runbook
   *before* SSO is switched on.
3. **Group authenticates, local user row authorizes.** Entra group membership is
   necessary but not sufficient; the email must also match an **active** `users`
   row. **No auto-provisioning** and **no group-to-role mapping** — roles stay in
   CAPRI's admin screen, where the business owner can see and change them
   without an IT ticket.
4. **Fail closed on configuration, fail open on the flag.** An incomplete config
   with the flag on behaves as SSO-off and logs a startup `WARNING`. This is the
   *safe* failure rather than the *secure* one, chosen because a typo should not
   lock every user out of a working app.
5. **Sessions are unchanged.** The same Flask-Login session and cookie. We record
   `session["auth_method"] = "sso"` and use it only where behaviour genuinely
   differs.

## 3. Architecture

Approach: a service module plus routes on the existing auth blueprint. This
follows CAPRI's own "keep routes thin, put logic in `services/`" rule and mirrors
APEX, so the two apps stay reviewable against each other.

```
frontend/src/routes/LoginPage.tsx      tri-state login screen
        |  GET /api/auth/config        {"ok": true, "sso_enabled": bool}
        |  GET /api/auth/sso/login     -> 302 Entra
        |  GET /api/auth/sso/callback  <- 302 back with ?code=
        v
app/blueprints/auth.py                 thin routes, the 403, the redirects
        v
app/services/sso_service.py            the ONLY module importing msal
        v
app/models.User                        the row that authorizes
```

### 3.1 `app/services/sso_service.py`

Pure functions over claim dicts and `User` rows, which is what makes every gate
testable without a network.

| Function | Behaviour |
|---|---|
| `sso_config()` | The six env vars, read from `os.environ` **at call time**. Returns a dict only when the flag is `1` *and* every value is present, including at least one group; otherwise `None`. |
| `build_auth_flow(cfg)` | `initiate_auth_code_flow(scopes=[], redirect_uri=cfg["redirect_uri"])`. |
| `redeem(cfg, flow, args)` | `acquire_token_by_auth_code_flow` wrapped in a broad `except` to `SsoError("auth_failed")`. |
| `resolve_user(cfg, claims)` | The four gates below. Returns a `User`. Takes `cfg` because gate 2 intersects against `cfg["groups"]`. |
| `safe_next_path(value)` | A same-origin path, or `""`. |
| `_client(cfg)` | The one seam the tests fake. Everything else runs for real. |

`SsoError(code, detail="")` asserts its code is in a fixed `ERROR_CODES` tuple.
Codes reach the browser in a query string, so the vocabulary is fixed
server-side and **never interpolated text** — no exception message, claim value
or email address may leak that way. The `detail` is logged, never returned.

**Scopes are `[]`.** CAPRI calls nothing on the user's behalf, so no token is
stored, refreshed or protected — everything except `id_token_claims` is
discarded as soon as the claims are read.

Note that `[]` does **not** mean the authorize request asks for nothing: MSAL
decorates whatever you pass with `openid profile offline_access`, and there is
no supported way to suppress that through `initiate_auth_code_flow`. Verified
against the live tenant on 2026-09-21 — the wire scope is
`offline_access openid profile`, so a refresh token **is** issued. Nothing
reads or stores it and it dies with the response object, but "we never ask for
one" would be untrue and the code must not claim it.

**No hand-rolled token validation.** `acquire_token_by_auth_code_flow` checks the
signature against the tenant's JWKS, plus issuer, audience, nonce and state.
Reimplementing any of it is how signature checks get accidentally disabled.

### 3.2 The four gates, in order

The order is the guide's, not the obvious one: each code names a **different
person** to act on it, so running them out of order hands an IT problem to an app
admin.

1. `claims["groups"]` is not a list, giving **`no_groups_claim`** *(IT: token
   configuration)*. `None` is not "member of nothing" — Entra omits `groups` and
   emits `_claim_names` once a user is in enough groups, so an absent claim is
   indistinguishable from an empty one. Treating it as a pass would silently
   disable this gate for exactly the most-connected accounts.
2. No intersection with `cfg["groups"]`, giving **`not_in_group`** *(IT: access
   request)*.
3. No `User` row for the email, giving **`unknown_user`**; row found but `active`
   is false, giving **`inactive_user`** *(app admin)*. The email is lowercased and
   read from `preferred_username` with `email` as fallback — which of the two
   Entra populates depends on how the account was created, so reading only the
   first refuses a real subset of accounts as unknown.
4. `user.entra_oid` is set and differs from `claims["oid"]`, giving
   **`identity_mismatch`**. If unset and an `oid` is present, it is pinned now.
   The email matched but the person did not; refuse rather than hand over a role,
   a division scope and authorship of approval-history rows.

Gate 4 is APEX's addition, not the guide's. It is worth the column in CAPRI
because `ApprovalAction` is an attributable audit trail.

### 3.3 Routes on `app/blueprints/auth.py`

The blueprint already owns `/api/auth`, and the guide mandates these exact paths
because every D&H login screen reads them.

- **`GET /config`** returns `{"ok": true, "sso_enabled": ...}`. Unauthenticated,
  because `/api/auth/me` 401s before login and the login screen has no other way
  to learn which form to draw. It leaks one boolean that is visible from the page
  anyway. Safe under `_require_password_change`, which only fires for
  authenticated users.
- **`GET /sso/login`** 404s when off. Stores `session["sso_flow"]` and
  `session["sso_next"]`, redirects to `flow["auth_uri"]`. On an MSAL exception it
  redirects to the login screen, never 500s.
- **`GET /sso/callback`** 404s when off. `session.pop` the flow, redeem, run the
  gates, `login_user(user, remember=False)`, `session["auth_method"] = "sso"`,
  redirect to the stored next path or `/`.
- **`POST /login`** gains the 403 as its **literal first line**, before
  `get_json`, the database or bcrypt. A credential-stuffing run then costs one
  string comparison per request instead of a hash.

Both SSO routes 404 rather than 403 when the flag is off: with SSO off these
entry points do not exist. `session.pop` rather than `get` because a flow is
single-use — leaving it in the session invites replay. A missing flow fails
closed to `auth_failed`, never a partial sign-in.

## 4. CAPRI-specific adaptations

Five places where CAPRI differs from both the guide and APEX. Each is a real
constraint of this codebase, not a preference.

### 4.1 Failures redirect to `/login?sso_error=...`, not `/?sso_error=...`

The guide sends every failure to `/`. In CAPRI `/` is inside `ProtectedLayout`,
which redirects an unauthenticated visitor to `/login?next=/` — **discarding the
error code**, so the user would see a bare login screen with no explanation.
CAPRI targets `/login` directly.

### 4.2 `_require_password_change` skips SSO sessions

`app/__init__.py`'s `before_request` 403s the whole API for a
`must_change_password` user, exempting only the set-password endpoints. Under
SSO-only there is no password form to escape through, so an admin-created user
would be locked out of everything with no route forward. The guard gains
`session.get("auth_method") == "sso"` as a skip condition.

Its frontend counterpart: `_user_json` grows an **`auth_method`** field
(`"sso"` or `"password"`), because `auth/ProtectedLayout.tsx:13` independently
redirects on `must_change_password` and would otherwise send SSO users to
`/change-password` to invent a password nothing uses.

### 4.3 `response_mode` stays at MSAL's default (query/GET)

CAPRI sets `SESSION_COOKIE_SAMESITE = "Lax"`, which does not send the cookie on a
cross-site POST. A `form_post` callback would therefore arrive with no session,
the flow dict would be unreachable, and **every** sign-in would fail while
looking exactly like an Entra misconfiguration. Do not change this.

Relatedly, CSRF is a non-issue here: `CSRFProtect` only guards mutating verbs and
both new routes are GETs — which is necessary, since a redirect arriving from
Entra could not carry an `X-CSRFToken`.

### 4.4 SSO config is not a `Config` class attribute

`app/config.py` assigns config at **import** time (`DevConfig.SQLALCHEMY_DATABASE_URI
= _database_url(...)`). SSO config must not follow that pattern: guide §5 and §9.1
require request-time `os.environ` reads so the suite can flip the config per test
with `monkeypatch`. `sso_config()` is therefore a function in the service module,
and the reason gets a comment, as `config.py` already does for its double
`quote_plus`.

### 4.5 `remember=False` for SSO sessions

The password path keeps `remember=True` and its 30-day cookie. SSO sessions do
not, because centralised revocation is much of the point of SSO: a 30-day
remember cookie would keep someone in CAPRI for weeks after Entra access was
withdrawn. Email deep links still work — the link lands on `/login`, one click on
the Microsoft button re-authenticates silently against the existing Entra session,
and `?next=` delivers the original destination. The cost is one click after a
browser restart, accepted deliberately.

## 5. Error vocabulary

Six codes. Each message names **who fixes it**, which is what keeps this feature
from generating support traffic.

| Code | Frontend message | Fixed by |
|---|---|---|
| `no_groups_claim` | Microsoft sign-in succeeded but no group information was returned. Contact IT. | IT |
| `not_in_group` | Your Microsoft account isn't in the authorized security group. Contact IT to request access. | IT |
| `unknown_user` | Your Microsoft account isn't set up in CAPRI yet. Ask an admin to add your user. | App admin |
| `inactive_user` | Your account is deactivated. Contact an admin. | App admin |
| `identity_mismatch` | This Microsoft account doesn't match the account on file for your email address. Contact IT. | IT |
| `auth_failed` | Microsoft sign-in failed or was cancelled. Please try again. | User, then IT |

Every failure is a **redirect** to the login screen, never a JSON error: the
browser is doing a top-level navigation, and a JSON body renders as a blank page
with text on it.

## 6. Frontend

### 6.1 `LoginPage` is tri-state, via TanStack Query

CAPRI already has Query 5, and `isPending` *is* the third state, so it needs no
extra bookkeeping where the guide uses `useState` plus `useEffect`:

```tsx
const { data, isPending } = useQuery({
  queryKey: ['auth-config'], queryFn: getAuthConfig, retry: false,
})
const ssoEnabled = isPending ? null : (data?.sso_enabled ?? false)
```

- `null` gives "Loading sign-in options…"
- `true` gives **only** the Microsoft button; the email/password form is not rendered
- `false` gives today's form, untouched

Defaulting to `false` would flash a password form that then vanishes, which reads
as a broken app and trains users to type credentials into a disappearing form.
`?? false` is the guide's `catch` to `false`: if the call fails the server is
probably down, and the password form at least produces a comprehensible error.

### 6.2 The button, and the deep link

A real navigation (`window.location.assign`), not a `fetch` — it is a top-level
redirect to Entra:

```tsx
`/api/auth/sso/login?next=${encodeURIComponent(safeNext(searchParams.get('next')))}`
```

Validated on both ends: `safeNext` client-side and `safe_next_path` server-side.

A small four-colour Microsoft mark is inlined in `LoginPage` rather than added to
`NavIcons`/`ActionIcons` — those are `currentColor` line icons on a 24px grid, and
Microsoft's mark must keep its official colours.

### 6.3 Error display

Read `sso_error`, map it through §5, then strip the parameter with
`setSearchParams(next, { replace: true })` — preserving any `next` alongside it —
so a refresh does not resurrect a stale error.

## 7. Open-redirect guard

`safe_next_path` is mandatory because `/sso/login` is reachable before anyone has
signed in, so whatever it is handed must be treated as hostile. A pre-auth
endpoint that redirects wherever it is told is a phishing primitive on our own
domain: the link genuinely starts at our hostname, survives a careful look, and
lands on a login clone.

Returns `""` unless the value starts with `/`, does not start with `//`, and
contains no backslash, CR or LF. A `//host` value, or a backslash some browsers
normalise to `/`, would redirect to another host entirely.

## 8. Data model

**Two** Alembic revisions on top of `e7f8a9b0c1d2`, in two commits. They are
unrelated changes — one is a pre-existing bug, the other is this feature — and
CLAUDE.md's "don't batch several unrelated changes into one commit" rule applies.
The `reset_token` fix goes **first**, since it is the prerequisite.

### 8.1 `users.entra_oid`

`String(36)`, nullable, **not unique** — matching APEX's `entra_oid TEXT`.
Existing rows are NULL and get pinned on first SSO sign-in. Gate 4 finds the row
by email and compares, so uniqueness is not needed for correctness.

### 8.2 Fixing `users.reset_token` (prerequisite, found 2026-09-21)

**CAPRI cannot currently hold more than one user on Azure SQL.** `reset_token` is
declared `unique=True, nullable=True` (`models/__init__.py:78`). SQLite permits
many NULLs, so dev works with 19 users; SQL Server treats NULLs as equal in a
UNIQUE index and permits exactly **one**. Verified against the dev server — a
second user with a NULL `reset_token` fails:

```
IntegrityError: Violation of UNIQUE KEY constraint 'UQ__users__25F405EB36267CDA'.
The duplicate key value is (<NULL>).
```

This is why the Azure database holds 1 user while SQLite holds 19 — not an
incomplete seed. It is pre-existing and unrelated to SSO in origin, but it is
**guide §3 prerequisite #1**: gate 3 requires every SSO user to have a row, so SSO
against Azure SQL cannot work for a second person until it is fixed. `reset_token`
is the only affected column in the schema.

The fix preserves the original intent rather than dropping it, following the
dialect-branching pattern already established in
`c2d3e4f5a6b7_drop_legacy_approver_columns.py`:

- **SQLite:** `batch_alter_table` recreates the table without the inline UNIQUE,
  then an ordinary unique index — multiple NULLs are already legal there.
- **SQL Server:** the constraint is a real `UNIQUE_CONSTRAINT` (verified: it
  appears in `sys.key_constraints` with `type='UQ'`, not merely as a unique
  index), so resolve its name by joining `sys.key_constraints` to
  `sys.index_columns`/`sys.columns` on `unique_index_id`, then
  `op.drop_constraint(name, "users", type_="unique")`. The name must be looked
  up, never assumed — it is auto-generated (`UQ__users__25F405EB36267CDA` on the
  dev server) and differs per database, which is exactly the failure `f3ed810`
  fixed for a foreign key. Skip the drop when the lookup finds nothing, as that
  migration already does. Then create a **filtered** unique index carrying
  `mssql_where="reset_token IS NOT NULL"` — the standard SQL Server idiom for a
  nullable-unique column.

The downgrade restores the plain constraint.

## 9. Environment variables

Six, prefix `CAPRI_`. Only the secret is a secret; tenant, client ID, group IDs
and redirect URI are identifiers, not credentials.

| Variable | Purpose |
|---|---|
| `CAPRI_ENABLE_SSO` | `1` turns SSO on and makes it the only login method. |
| `CAPRI_SSO_TENANT_ID` | Directory (tenant) ID |
| `CAPRI_SSO_CLIENT_ID` | Application (client) ID |
| `CAPRI_SSO_CLIENT_SECRET` | Client secret — Key Vault or `.env`, never git |
| `CAPRI_SSO_ALLOWED_GROUPS` | Comma-separated group **object IDs** |
| `CAPRI_SSO_REDIRECT_URI` | The exact registered redirect URI for this environment |

All six live in `backend/.env` locally, which is git-ignored and must stay so —
the repository mirrors to GitHub.

## 10. Entra requirements

CAPRI needs **its own app registration** (guide §4: redirect URIs and secret
rotation are per-app; sharing one means another app's rotation breaks CAPRI).

- **One redirect URI** for now: `http://localhost:5100/api/auth/sso/callback`.
  CAPRI is single-server on one port, where APEX needed three. Entra matches
  literally — scheme, host, port, path, no trailing slash.
- **`SEC-App-Capri-Dev`** is the authorizing group. Bryan owns it, so its object
  ID and membership are not an IT ask; **assigning it to the app registration**
  is, since that needs rights over the registration.
- **The `groups` claim must be emitted**, via Token configuration to *Groups
  assigned to the application*. Prefer that over *All groups*: with all groups a
  user in many groups overflows the claim and Entra sends a link instead of the
  list, so the claim goes missing for exactly the most-connected users.
- **Someone owns the client secret expiry date** with a calendar reminder. An
  expired secret is a total outage with no in-app warning.

`CAPRI_SSO_ALLOWED_GROUPS` takes **object IDs (GUIDs), not display names.**
Pasting `SEC-App-Capri-Dev` fails every sign-in at gate 2 as `not_in_group`,
which reads as an access-request problem and sends you to IT for a one-line typo.

**No deployed HTTPS environment yet.** Entra permits plain `http://` only for
`localhost`, so when CAPRI is deployed it will need a DNS name and HTTPS before
SSO can be enabled there — a bare `http://172.16.x.x:port` cannot be registered
at all. This blocked ARIA's production SSO for months and has already bitten
APEX. Until then that environment keeps `CAPRI_ENABLE_SSO=0`, which §2.4 gives
us for free.

A sendable version of all this is a deliverable of this work:
`docs/it-requests/2026-09-21-capri-entra-sso.md`, modelled on the equivalent in
the APEX repo (`../apex/docs/it-requests/2026-09-21-entra-sso-email.md`, which
lives in that repository, not this one).

## 11. Testing

`msal>=1.20` into `requirements.txt`.

### 11.1 The ambient-`.env` trap

`app/config.py` calls `load_dotenv()` at import. A developer whose `.env` has
`CAPRI_ENABLE_SSO=1` would make **every password-login test in the suite** 403,
and *which* tests fail would shift as tests were added, because it depends on
import order. `tests/conftest.py` gains an autouse fixture that pops
`CAPRI_ENABLE_SSO` and the five `CAPRI_SSO_*` vars and restores them afterwards;
SSO tests opt back in with `monkeypatch`.

The guide's "load-bearing import" is already satisfied here — `conftest.py`
imports `create_app`/`TestConfig` at module scope, so `load_dotenv()` has run
before any fixture body executes.

### 11.2 `tests/test_sso.py`

Monkeypatch the single `_client` seam; everything else runs for real. We are
testing our gates, not Microsoft's protocol.

| Test | Asserts |
|---|---|
| Config requires the flag **and** every value | Each variable removed in turn yields `None` |
| `GET /api/auth/config` | Reports true/false matching the config |
| `/sso/login` | 302 to Entra, flow stored in the session |
| `/sso/login` on an MSAL error | Redirects to the login screen, not a 500 |
| Both SSO routes when SSO off | 404 |
| Callback success | Session established, `auth_method == "sso"`, remember cookie absent |
| Callback rejections | One case per gate, each giving the right `sso_error` code |
| Gate 4 both ways | Mismatched `oid` refused; absent `entra_oid` pinned on first sight |
| Inactive user | `inactive_user`, no session |
| Callback with no flow in session | Fails closed to `auth_failed` |
| Password login when SSO on | **403** |
| Password login on an incomplete config | Still works (the §2.4 rule) |
| `safe_next_path` | Accepts `/a/b?c=d`; rejects `//evil.com`, `https://evil.com`, backslashes, CR/LF |
| Deep link round trip | `?next=` in, that path out |
| Off-site `next` | Lands on `/`, not the attacker |

Plus: `test_password_change.py` gains the SSO-session skip case; a migration test
that `entra_oid` exists and that the migration runs against a database predating
it; and frontend vitest for `LoginPage`'s three states and the `sso_error` map.

Full verification: backend `pytest -q` (336 existing plus new), `npm test`, and
`node ./node_modules/typescript/bin/tsc --noEmit -p tsconfig.json`.

### 11.3 What tests cannot prove

Every test fakes `_client`, so no real token is ever issued, signed, validated
or parsed. The claim shapes the gates depend on — `groups` as a list of GUID
strings, `preferred_username` vs `email`, the presence of `oid` — are taken
from the guide, not observed.

**Partially closed on 2026-09-21** by running the real
`msal.ConfidentialClientApplication` against the live D&H tenant authority
(no app registration needed for this much). That established: the flow carries
`state`, `nonce` and PKCE `S256`; `response_type=code`; `response_mode`
defaults to query as §4.3 requires; the redirect URI is emitted exactly; and a
bad tenant raises `ValueError`, which is the path `redeem`'s broad `except`
and the callback's `auth_failed` handler exist for. It also surfaced the
`offline_access` correction in §3.1 and MSAL's standing `UserWarning`
recommending the `form_post` mode that §4.3 forbids.

Still unproven, and only provable with a real registration: the token exchange
itself, every claim shape, and any actual sign-in. Once IT delivers the values,
verify by hand in the target environment: a group member with an app row signs in; a member
**without** a row sees `unknown_user`; a non-member sees `not_in_group`; a
deactivated user sees `inactive_user`.

## 12. Operations

`docs/sso-support-runbook.md`, written **before** SSO is ever switched on:

- **Recovery:** set `CAPRI_ENABLE_SSO=0` and restart. Locally one line in
  `backend/.env`. The moment you need this is the moment nobody can log in to
  look it up.
- The guide §11 failure table, and the rule that granting access is **two steps**
  — group membership *and* an active row in CAPRI.
- Which environment is in which mode, written down.

CLAUDE.md gains an SSO section covering the switch, the six variables, the four
gates and the `/login?sso_error=` divergence.

## 13. Rollout

Guide §10. **This spec delivers Step 0 only.**

| Step | What | Go/no-go |
|---|---|---|
| **0** | Ship all the code with the flag unset. SSO routes 404, nothing changes. | Password login works everywhere; SSO tests pass |
| **1** | Send the IT request; get the registration. Expect the long pole to be redirect URIs. | Five values in hand, `groups` claim confirmed |
| **2** | Hybrid in a lower environment only: temporarily skip the 403, flag on, a handful of real users sign in. | Every pilot user signs in; every rejection shows the right message |
| **3** | Restore the 403, enable the flag, announce. | All users have group **and** row; someone other than Bryan can perform the recovery |

Step 2 stays short and confined to a lower environment. A hybrid production app is
the configuration §2.1 exists to avoid.

## 14. Out of scope

- Enabling SSO anywhere. The flag ships unset.
- Auto-provisioning users, and any group-to-role mapping (§2.3).
- Hiding the admin password-reset or profile password UI when SSO is on. The
  backend endpoints stay, so the UI staying is consistent; revisit at Step 3.
- Graph API calls, access-token storage, refresh tokens.
- Deployment pipelines and Key Vault wiring — CAPRI has no deployed environment
  yet. Guide §8 applies when it does.
- Clearing `must_change_password` for SSO users. It is skipped, not cleared.
