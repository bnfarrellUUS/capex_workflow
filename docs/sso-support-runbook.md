# CAPRI SSO — support runbook

**Spec:** `docs/superpowers/specs/2026-09-21-capri-entra-sso-design.md`
**Guide:** `docs/entra-sso-implementation-guide.md`

---

## 1. Emergency: nobody can sign in

**Set `CAPRI_ENABLE_SSO=0` and restart.**

Locally that is one line in `backend/.env` — comment it out or set it to `0`,
then restart the Flask server. Password login comes straight back for everyone,
because the password endpoints, the login form and the admin password reset were
all deliberately left in place for exactly this.

This is at the top of the page on purpose: **the moment you need it is the moment
nobody can sign in to look it up.** Print it, or keep it somewhere that does not
require CAPRI to read.

There is **no in-app break-glass password**, not even for the admin account. A
bypass that exists for the admin is a bypass an attacker only has to find once,
and the admin account is the one worth taking. Recovery is operational, by
design.

Causes worth checking once everyone is back in: an Entra outage, an **expired
client secret** (no in-app warning — the app just refuses everyone), or a bad
configuration change.

---

## 2. Granting someone access is two steps

Both are required. Neither is sufficient alone.

| Step | What | Who does it |
|---|---|---|
| 1 | Membership of **`SEC-App-Capri-Dev`** | IT (Bryan owns the group) |
| 2 | An **active user row** in CAPRI with the same work email | CAPRI admin, via Admin → Users |

Step 1 decides whether someone may reach the app. Step 2 decides what they may
do inside it — role, division, approval routing. CAPRI deliberately does **not**
auto-create accounts and does **not** map Entra groups to roles, so a permission
change never becomes an IT ticket and a new hire in the group does not silently
acquire approval authority.

The email must match exactly (CAPRI lowercases before comparing).

---

## 3. Failure modes

Every refusal sends the user back to the login screen with a message that names
who fixes it. The code is in the URL as `?sso_error=<code>` until the page
strips it.

| Symptom / code | Actual cause | Who fixes it |
|---|---|---|
| `no_groups_claim` | Token configuration does not emit `groups`; or the claim overflowed because it is set to *All groups* rather than *Groups assigned to the application*; or the user is in no groups at all | IT |
| `not_in_group` | Signed in fine, but not a member of an authorizing group — **or** `CAPRI_SSO_ALLOWED_GROUPS` holds a display name or the wrong object ID | IT (access request, or the config typo) |
| `unknown_user` | No row in CAPRI for that email, or the email differs from the Entra one | CAPRI admin |
| `inactive_user` | The row exists but is deactivated | CAPRI admin |
| `identity_mismatch` | `users.entra_oid` was pinned to a different Entra identity — a recycled or reassigned address, or the row was pinned by the wrong person signing in first | IT to confirm identity, then CAPRI admin (see §4) |
| `auth_failed` | Cancelled at the Microsoft screen, an expired session, a replayed callback, or an MSAL error — most often a **redirect-URI mismatch** or an **expired client secret** | User retries, then IT |
| The Microsoft button never appears | `sso_config()` returned `None` — a missing variable. **Check the startup WARNING in the server log**, which names the missing ones | Deployer |
| Sign-in loops back to the login screen | The session cookie is not persisting — `SECRET_KEY` changing on restart, or a proxy stripping the cookie | Developer |
| The whole test suite 403s on login | A developer `.env` leaking into tests. The `_no_ambient_sso` fixture in `backend/tests/conftest.py` exists to prevent this; check it has not been removed | Developer |

`no_groups_claim` and `not_in_group` are deliberately **different codes**. A
missing claim is an IT token-configuration problem; a failed match is an access
request. Different people fix them, so collapsing both into "access denied"
would send half the tickets to the wrong team.

---

## 4. Clearing a wrongly pinned `entra_oid`

`users.entra_oid` is stamped on a user's **first** SSO sign-in and compared on
every one after, so a recycled or reassigned email address cannot inherit an
existing user's role, division scope and authorship of approval-history rows.

If it was pinned to the wrong identity, the user is stuck on
`identity_mismatch` and there is no in-app way out. Clear it:

```sql
UPDATE users SET entra_oid = NULL WHERE email = 'person@uniteduptime.com';
```

The next SSO sign-in re-pins it to whoever signs in.

**Confirm who the account actually belongs to first.** Clearing the column is
precisely the check being removed, so doing it without confirming defeats the
gate. If the mismatch is genuine — two different people, one email address —
the answer is a new user row, not a cleared column.

---

## 5. Which environment is in which mode

| Environment | Mode | Why |
|---|---|---|
| Local development | **Password login.** `CAPRI_ENABLE_SSO` unset | No Entra app registration yet; see `docs/it-requests/2026-09-21-capri-entra-sso.md` |
| Deployed | **Does not exist yet** | When it does, it needs a DNS name and HTTPS before SSO can be enabled — Entra accepts `http://` only for `localhost` |

Keep this table current. An environment in an unexpected mode gets reported as a
broken deployment by the next person.

---

## 6. The configuration, for reference

Six variables, all in `backend/.env` locally (git-ignored — the repo mirrors to
GitHub, so they must never be committed).

| Variable | Notes |
|---|---|
| `CAPRI_ENABLE_SSO` | `1` turns SSO on **and makes it the only login method**. Anything else, or an incomplete config, leaves password login as the only method |
| `CAPRI_SSO_TENANT_ID` | Directory (tenant) ID |
| `CAPRI_SSO_CLIENT_ID` | Application (client) ID |
| `CAPRI_SSO_CLIENT_SECRET` | The only actual secret here |
| `CAPRI_SSO_ALLOWED_GROUPS` | Comma-separated group **object IDs (GUIDs)**, never display names |
| `CAPRI_SSO_REDIRECT_URI` | Must match what is registered in Entra literally |

SSO is on only when the flag is `1` **and every value is present**. A partial
configuration behaves as SSO-off and logs a startup `WARNING` naming what is
missing — that is deliberate, so a typo cannot lock everyone out of a working
app.
