# CAPRI — Entra SSO: the app registration request

**Date drafted:** 2026-09-21
**App:** CAPRI — Capital Approval, Planning, Reporting & Investment (Flask + React)
**Pattern:** follows `docs/entra-sso-implementation-guide.md`, the same recipe
ARIA and APEX were built to.
**Code status:** the SSO code is **already merged and deployed with the flag
off** (guide §10 Step 0). Nothing is blocked on this request except turning it
on, and nothing changes for users until it is.

**Before sending:** fill in `[name]` and `[secure channel]`, and **attach the
CAPRI user list** so confirmation 3 has something to map against. The list is
deliberately not in this file: the repository mirrors to GitHub and staff
addresses do not belong in it.

---

## The two things that actually break sign-ins

Worth reading before the request itself, because both cost an afternoon each
when they go wrong and neither looks like its own cause.

**1. The `groups` claim has to be emitted.** Token configuration → *Groups
assigned to the application*, with the authorizing group assigned to the app.
Without it every sign-in fails at the first gate with `no_groups_claim`, which
reads as an application bug rather than a directory setting.

Please **not** *All groups*: a user in enough groups overflows the claim, and
Entra then sends a link to fetch the groups instead of the list itself. The
claim goes missing for exactly the most-connected people, which is a memorably
confusing bug to chase.

**2. `CAPRI_SSO_ALLOWED_GROUPS` takes object IDs (GUIDs), not display names.**
From Microsoft's documentation: *"By default group object IDs are emitted in the
group claim value."* CAPRI intersects the `groups` claim against that setting as
plain strings, so pasting `SEC-App-Capri-Dev` into it fails every sign-in at the
second gate as `not_in_group` — which reads as an access-request problem and
sends people to IT for what is a one-line configuration typo.

---

## What we need

**This is a request for a NEW app registration, not a change to ARIA's or
APEX's.** Guide §4: one app registration per application per tenant. The
redirect URIs and the secret rotation schedule are per-app, and sharing a
registration means one app's secret rotation breaks the others.

| # | Item | Env var it fills |
|---|---|---|
| 1 | Directory (tenant) ID | `CAPRI_SSO_TENANT_ID` |
| 2 | Application (client) ID | `CAPRI_SSO_CLIENT_ID` |
| 3 | Client secret — **please share via a secure channel, not email** | `CAPRI_SSO_CLIENT_SECRET` |
| 4 | Object ID of the authorizing security group | `CAPRI_SSO_ALLOWED_GROUPS` |
| 5 | The exact redirect URI registered on the app | `CAPRI_SSO_REDIRECT_URI` |

Values go into the app's local environment (`backend/.env`, git-ignored).
**Never in git** — the repository mirrors to GitHub.

## The security group

`SEC-App-Capri-Dev`, following the `SEC-App-<App>-<Env>` convention. **Bryan
owns this group**, so its object ID and its membership are his to read and
manage — neither is an IT ask.

What **is** an IT ask: **assigning `SEC-App-Capri-Dev` to the new app
registration**, which needs rights over the registration rather than over the
group. Without that assignment the group never appears in CAPRI's tokens at
all, regardless of who is in it.

## Redirect URI to register

**One URI**, exactly as written — CAPRI runs as a single Flask server that
serves both the API and the built React app on one port, so unlike APEX there is
only one to register:

```
http://localhost:5100/api/auth/sso/callback
```

Entra matches these **literally**: scheme, host, port, path, no trailing slash.

**There is no deployed environment to register yet.** When CAPRI is deployed it
will need a **DNS name and HTTPS** first: Entra accepts plain `http://` only for
`localhost`, so a bare LAN address such as `http://172.16.32.70:8081` cannot be
registered at all. This is the same wall APEX hit on 2026-09-21 and the one that
held ARIA's production SSO up for months, so it is worth planning for before
CAPRI is deployed rather than after. Until then that environment simply runs
with SSO off and keeps password login, which the app's fail-closed rule gives us
for free.

## Please confirm

- [ ] **The `groups` claim is emitted in ID tokens** — Token configuration →
      *Groups assigned to the application* (not *All groups*), with
      `SEC-App-Capri-Dev` assigned to the app registration.
- [ ] **The redirect URI above is registered**, exactly.
- [ ] **Intended users are in `SEC-App-Capri-Dev`.** Note that group membership
      alone is not enough — see below.
- [ ] **Someone owns the client secret expiry date**, with a calendar reminder.
      An expired secret is a total outage with no in-app warning and an error
      that points at the app rather than at the secret.

## How access works, so the right team gets the right ticket

Granting someone access to CAPRI is **two steps**, deliberately:

1. **Membership of `SEC-App-Capri-Dev`** — IT's side. This is what says a person
   may reach the app at all.
2. **An active user row in CAPRI with the same work email** — the app admin's
   side. This is what says what they may *do*: their role, their division, their
   place in the approval routing.

CAPRI does not auto-create accounts and does not map Entra groups to roles, so
that a permission change never becomes an IT ticket and a new hire in the group
does not silently acquire approval authority. The error messages name which of
the two steps is missing:

| The user sees | What is missing | Who fixes it |
|---|---|---|
| "isn't in the authorized security group" | Group membership | IT |
| "isn't set up in CAPRI yet" | The user row | App admin |
| "your account is deactivated" | The row is inactive | App admin |
| "no group information was returned" | The `groups` claim configuration | IT |

---

**Subject:** CAPRI SSO — app registration request

Hi [name],

We'd like to put CAPRI (our capital-expenditure approval app) behind Entra SSO,
the same way ARIA is and APEX is being set up. The code is already written and
deployed with the feature switched off, so this request is the only thing
between us and turning it on — and nothing changes for users until we do.

Could you please create **a new app registration for CAPRI** and send back:

1. Directory (tenant) ID
2. Application (client) ID
3. A client secret — via [secure channel] rather than email, if you don't mind
4. The object ID of `SEC-App-Capri-Dev`
5. Confirmation of the registered redirect URI

The redirect URI to register is exactly:

    http://localhost:5100/api/auth/sso/callback

Two settings on the registration matter more than they look:

- Under **Token configuration**, please add the **groups claim** set to
  **"Groups assigned to the application"**, and assign `SEC-App-Capri-Dev` to
  the app. Without this the app gets no group information at all and refuses
  every sign-in. Please avoid "All groups" — for users in many groups Entra
  replaces the list with a link, and the claim effectively goes missing for
  exactly those people.
- I need the group's **object ID (the GUID)**, not the display name. The app
  compares the GUID from the token, so a display name silently fails every
  sign-in with what looks like an access-permissions error.

I already own `SEC-App-Capri-Dev`, so I can manage who's in it — the only thing
I can't do myself is assign it to the new registration.

One note for later: we'll eventually want CAPRI on a proper hostname with HTTPS
before we can enable SSO anywhere other than a developer machine. Entra only
accepts `http://` for `localhost`, so an internal IP and port can't be
registered as a redirect URI. No action needed now, but worth knowing when we
talk about hosting it.

Finally, could you note who owns the **client secret's expiry date** and set a
reminder? When one of these expires the app fails every sign-in with an error
that looks like our bug rather than an expired credential.

I've attached the list of people who'll need access.

Thanks,
Bryan
