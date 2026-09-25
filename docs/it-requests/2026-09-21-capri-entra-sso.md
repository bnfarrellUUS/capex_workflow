# CAPRI — Entra SSO: the app registration request

**Date drafted:** 2026-09-21
**App:** CAPRI — Capital Approval, Planning, Reporting & Investment (Flask + React)
**Pattern:** follows `docs/entra-sso-implementation-guide.md`, the same recipe
ARIA and APEX were built to.
**Code status:** the SSO code is **already merged and deployed with the flag
off** (guide §10 Step 0). Nothing is blocked on this request except turning it
on, and nothing changes for users until it is.

**Status:** **sent 2026-09-21 16:08** to Jordan St. Clair (cc Joe Loner, Eric
Arnold, Jessica Beltran), as drafted below. Follow-up sent on the same thread
2026-09-25 14:25 UTC (at the bottom); no reply from IT yet. Jordan's reply on the parallel APEX thread (2026-09-21 17:50) set
IT's approach, which the follow-up at the bottom adopts: SSO values live in Key
Vault and are read at deploy time (never sent to Bryan), and sign-in is
validated against the Dev environment rather than localhost.

**Before sending:** **attach the CAPRI user list**, which is what makes the UPN
question answerable per account. The list is deliberately not in this file: the
repository mirrors to GitHub and staff addresses do not belong in it.

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

## Redirect URIs to register

**Two URIs**, exactly as written. CAPRI runs as a single Flask server that
serves both the API and the built React app on one port, so unlike APEX there is
one per environment:

```
http://localhost:5100/api/auth/sso/callback
https://capri-dev.uniteduptime.com/api/auth/sso/callback
```

Entra matches these **literally**: scheme, host, port, path, no trailing slash.

**The second is the Dev hostname requested on 2026-09-25** (ADO 5891, in the
"CAPRI Dev: Container App environment" email). If IT picks a different name,
register that instead. Entra accepts plain `http://` only for `localhost`, so
the Dev environment needs its DNS name and HTTPS in place before SSO can work
there. That's the same wall APEX hit on 2026-09-21, and the one that held ARIA's
production SSO up for months. Until then Dev simply runs with SSO off and keeps
password login, which the app's fail-closed rule gives us for free.

## Please confirm

- [ ] **The `groups` claim is emitted in ID tokens** — Token configuration →
      *Groups assigned to the application* (not *All groups*), with
      `SEC-App-Capri-Dev` assigned to the app registration.
- [ ] **Both redirect URIs above are registered**, exactly.
- [ ] **Intended users are in `SEC-App-Capri-Dev`.** Note that group membership
      alone is not enough — see below.
- [ ] **Someone owns the client secret expiry date**, with a calendar reminder.
      An expired secret is a total outage with no in-app warning and an error
      that points at the app rather than at the secret.
- [ ] **The exact UPN of every intended user** — see "The UPN trap" below. This
      is the one that silently locks people out, and it is not per-app: one
      answer covers CAPRI, APEX and anything after.

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

## The UPN trap (added 2026-09-21, after checking)

**Resolved 2026-09-25:** most UPNs are @dh-united.com (Bryan), and the Dev
database's real user records already use @dh-united.com, so they match. New
users must be added with their @dh-united.com UPN as their email. The counts
quoted below were from a local database, not Dev.

**This is the item most likely to break CAPRI, and it is not in the guide.**

Gate 3 matches the `preferred_username` claim — which Entra populates with the
**UPN** — against `users.email` in CAPRI. Those are not the same thing here.
Checked against Microsoft Graph on 2026-09-21, Bryan's own account resolves as:

| Field | Value |
|---|---|
| `userPrincipalName` | `bryan.farrell@dh-united.com` |
| `mail` | `bryan.farrell@uniteduptime.com` |

So **`dh-united.com` looks like the real UPN suffix and `uniteduptime.com` the
mail domain** — the opposite of the assumption in APEX's 2026-09-18 note.

CAPRI's user records are currently **16 `@uniteduptime.com`, 2
`@tanknology.com`, 1 `@dh-united.com`**. If UPNs really are `@dh-united.com`
across the board, almost every user is refused at sign-in with `unknown_user`,
and there is no password fallback once SSO is on.

**Do not enable SSO until the UPN for each account is confirmed and the
`users.email` values are corrected to match.** The `@tanknology.com` pair may
not be in this tenant at all and needs its own answer.

Related: the Azure SQL dev database currently holds only **2** user rows
(`admin@uniteduptime.com` and `bryan.farrell@dh-united.com`). The other 17 exist
only in the local SQLite file, so they would need migrating before SSO is usable
against Azure regardless of the UPN answer.

---

## The email as sent (2026-09-21 16:08)

**To:** Jordan St. Clair · **Cc:** Joe Loner, Eric Arnold, Jessica Beltran
(the same recipients as the APEX request sent 2026-09-21 14:28)

**Subject:** CAPRI — new Entra app registration needed (5 values + 3 confirmations)

Hi Jordan,

Second one of these today, sorry — this is the same request as the APEX email I
sent this morning, but for CAPRI (our capital-expenditure approval app).
Separate app registration, separate thread so it's easier to track. **Two of the
questions from the APEX email cover both apps**, so please answer those once and
I'll apply them to each: the UPN-suffix question, and whether the convention
here is one registration per environment or one per app.

As with APEX: the code is written and deployed with SSO switched off, so nothing
changes for anyone until this is in place and I've done a test sign-in myself.

**The UPN question, with a concrete data point**

This is the one that will break CAPRI if we get it wrong, and I now have
evidence that sharpens what I asked this morning. My own account resolves as:

- userPrincipalName: `bryan.farrell@dh-united.com`
- mail: `bryan.farrell@uniteduptime.com`

So it looks like **dh-united.com is the real UPN suffix and uniteduptime.com is
the mail domain** — the opposite of what I guessed in the APEX email. That
matters because CAPRI matches a sign-in on the UPN that Entra puts in the token,
against the email address stored on the user's record in the app. CAPRI's
records are currently 16 @uniteduptime.com, 2 @tanknology.com and 1
@dh-united.com, so if UPNs really are @dh-united.com across the board, almost
every user would be refused at sign-in — and there is no password fallback once
SSO is on.

So, for the attached list, could you send **the exact UPN for each account**, or
just the rule for deriving it if there is one? I'll correct the records before
anything is switched on. Same question as APEX #2 — one answer does both apps,
and I don't need it per-app.

The @tanknology.com pair may be a separate case again; if those aren't in this
tenant at all, tell me and I'll handle them differently.

**The request: a new app registration for CAPRI**

Not a change to ARIA's or APEX's — redirect URIs and secret rotation are
per-app, so sharing a registration means one app's secret rotation breaks the
others.

What I need from you:

1. Directory (tenant) ID
2. Application (client) ID
3. Client secret — please send through a secure channel, not email, and tell me
   the expiry date
4. `SEC-App-Capri-Dev` assigned to the new registration. I own the group, so
   I'll manage membership and I already have its object ID — but assigning it to
   the app needs rights over the registration, which is yours. Same
   easy-to-miss step as APEX: with "Groups assigned to the application", a group
   only appears in the tokens of apps it is actually assigned to.
5. Confirmation of the redirect URI you've registered

**Redirect URI to register.** Just one for CAPRI — unlike APEX, it runs as a
single server on one port, so there's only the one way in. Entra matches
literally: scheme, host, port, path, no trailing slash.

    http://localhost:5100/api/auth/sso/callback

**Three things to confirm:**

1. Token configuration emits the groups claim in ID tokens — please use "Groups
   assigned to the application", not "All groups". Same reasoning as the APEX
   email: with "All groups", anyone in roughly 200+ groups overflows the claim
   and Entra sends a link instead of the list, so it goes missing for exactly
   the most-connected people. Without the claim CAPRI fails closed for everyone,
   and the error looks like an application bug rather than a directory setting.
2. The group object ID is what I need for `SEC-App-Capri-Dev`, not the display
   name. CAPRI compares the GUID that arrives in the token, so a display name
   silently fails every sign-in with what reads like an access-permissions
   problem.
3. Whether you want one registration or two (the APEX question #3). If the
   convention is per-environment, the localhost URI above belongs on a Dev
   registration and we can set up Prod when CAPRI has a hostname. Just tell me
   the shape and I'll match it.

**One more:** who owns the client secret's expiry date? Same as APEX — an
expired secret is a full outage with no warning and nothing diagnosable from
inside the app, so I'd like a named owner and a calendar reminder.

**For later, not now:** CAPRI has no deployed environment yet. When it gets one
it'll need a DNS name and a certificate before SSO can work there, since Entra
only accepts http:// for localhost. That's the same DNS/HTTPS dependency APEX is
waiting on, so it may be worth solving once and covering both — but it doesn't
block anything here.

Thanks,
Bryan

**Before sending:** attach the CAPRI user list (deliberately not in this repo —
it mirrors to GitHub) and let Outlook add your signature.

---

## Follow-up (sent 2026-09-25 14:25 UTC) — reply on the 2026-09-21 thread

Short, and aligned with Jordan's APEX reply. **The UPN question is settled and
no longer asked:** Bryan confirmed on 2026-09-25 that most users' UPNs are
@dh-united.com, and every real user record on the Dev database (4 of 5) is
already @dh-united.com. The fifth is the seeded `admin@uniteduptime.com`,
which is deactivated at first deploy anyway. The group (exact display name
**SEC-App-CAPRI-Dev**) has 4 members on 2026-09-25 -- Andre Doerfer, Bryan
Farrell, Chris Jodlowski, Joe Loner -- and each has an active Dev user record
under their @dh-united.com UPN. The DNS record for
`capri-dev.uniteduptime.com` already exists (Jordan, 2026-09-22, pointing at the
Dev App Gateway, 172.16.32.70).

> Jordan,
>
> Following up on this one now that the CAPRI Dev environment request has gone
> out (this morning). I'm taking your APEX approach: values in Key Vault and SSO
> tested against Dev, not localhost. So this is much shorter than my original,
> and two of its questions are answered:
>
> - **The group is ready.** SEC-App-CAPRI-Dev has its 4 members (Andre Doerfer,
>   Joe Loner, Chris Jodlowski and me), and each already has an active CAPRI
>   account.
> - **No need to answer the UPN question.** CAPRI's accounts are already under
>   the @dh-united.com UPNs, so sign-ins will match.
>
> What's left on your side:
>
> 1. **Redirect URI** on the CAPRI app registration:
>    https://capri-dev.uniteduptime.com/api/auth/sso/callback (the DNS record you
>    added on the 22nd). The localhost one isn't needed.
> 2. **Groups claim** set to "Groups assigned to the application", and
>    **SEC-App-CAPRI-Dev assigned** to the registration. Those two were the last
>    things holding up APEX, so worth doing up front.
> 3. **Key Vault**, for the CAPRI Dev container: CAPRI_SSO_TENANT_ID,
>    CAPRI_SSO_CLIENT_ID, CAPRI_SSO_CLIENT_SECRET, CAPRI_SSO_ALLOWED_GROUPS (the
>    group's object ID from its Details tab, not its name) and
>    CAPRI_SSO_REDIRECT_URI (the URI above).
> 4. Leave **CAPRI_ENABLE_SSO** unset for now. I'll ask for it to be set to 1
>    once Dev is up and I've signed in with a password first.
>
> And when you create the client secret, could you let me know its expiry date?
>
> Thanks,
> Bryan
