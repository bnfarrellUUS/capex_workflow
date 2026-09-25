# Deploying CAPRI

Target: **Azure Container Apps**, one app per environment, following APEX's
pattern (`apex/docs/operations/deploy.md`). Settings are environment variables
on the Container App; secrets come from Key Vault through the Container App's
`secret` block. Work is tracked on Azure DevOps Boards, FinanceApps area
`Solutions\CAPRI`: **5879** (code), **5880** (Dev environment), **5881**
(Entra SSO).

| | Dev |
|---|---|
| Container App | `ca-capri-dev` *(proposed)* |
| Resource group | `uus-capri-dev-scus-rg` *(proposed)* |
| Registry | `uuscapridevscusacr` *(proposed)* |
| Pipeline | `pipelines/azure-pipelines-dev.yml`, every push to the Azure repo's `dev` branch |
| URL | `https://capri-dev.uniteduptime.com` *(proposed; VPN only, like APEX Dev)* |
| Database | Azure SQL `uus-capri-dev-scus-sql` (exists; private endpoint only) |
| Ingress target port | `8000` |
| Health probe path | `/api/health` |
| Replicas | **1** (see "One replica" below) |

*(proposed)* means named by analogy with APEX and not yet confirmed by IT.
Correct this table, and the variables in the pipeline, once IT has created the
resources.

**Where the settings are actually set.** The pipeline only builds the image and
swaps it in. It never sets a variable or a secret. The Container App, its
environment and its Key Vault references belong to IT's infrastructure
repository, so this file is the list of what CAPRI needs, and that repository
is where each setting has to exist. **No value for a secret is recorded here,
or anywhere in this repository**, which is mirrored to GitHub.

## Settings

**Secret** means Key Vault, never a plain environment value, the repository, or
the image.

### Core

| Variable | Required | Secret | Dev value | Notes |
|---|---|---|---|---|
| `APP_BASE_URL` | **yes** | no | `https://capri-dev.uniteduptime.com` | **The switch that makes this a deployed server.** Any non-localhost value selects the production config: secure-only cookies, no SQLite fallback, email off by default. It must be `https://`, or the app refuses to start. It is also the base of every link in notification emails, so it must be the final hostname. |
| `SECRET_KEY` | **yes** | **yes** | — | Signs the session cookie. A new random value just for this environment, never shared with another app. With a non-local `APP_BASE_URL`, the app **refuses to start** without it, or with the development key that is in the repo. Changing it signs everyone out. |

### Database

Set **one** of these two. With neither, the app refuses to start. There is no
fallback to an empty local database.

| Variable | Required | Secret | Dev value | Notes |
|---|---|---|---|---|
| `AZURE_SQL_ODBC` | **yes** (or `DATABASE_URL`) | **yes** | — | The **raw** ODBC connection string exactly as the Azure portal shows it (`Driver={ODBC Driver 18 for SQL Server};Server=…;Uid=…;Pwd=…;Encrypt=yes;…`). Do **not** URL-encode it: CAPRI encodes it itself, twice on purpose, because the password's `+ # ) !` characters are otherwise mangled (`backend/app/config.py`). Use CAPRI's own SQL user, not the server admin. The user needs DDL rights, because migrations run at container start. |
| `DATABASE_URL` | alternative | **yes** | leave unset | A full SQLAlchemy URL. If set, it wins over `AZURE_SQL_ODBC`. Only for a database that isn't Azure SQL. |

### Files

| Variable | Required | Secret | Dev value | Notes |
|---|---|---|---|---|
| `UPLOAD_ROOT` | **yes** | no | the Azure Files mount path | Where request attachments are stored. Unset, they go to the container's own disk, **which is wiped on every deploy and restart** while the database still points at them. Mount an Azure Files share and point this at it (ADO 5893). |

### Email

| Variable | Required | Secret | Dev value | Notes |
|---|---|---|---|---|
| `EMAIL_ENABLED` | no | no | `0` **until ADO 5884 ships** | `1` sends notification emails. **Today the only sender is the Outlook desktop app, which does not exist in a container.** Leave this at `0` (the default on a deployed server) until the SendGrid backend is in. Every notification is still recorded in the `NotificationLog` table either way. |
| `EMAIL_REDIRECT_TO` | no | no | an internal address | The **default** recipient for Test mode. Test/Live itself is an admin setting in the app (Admin → Email Templates), stored in the database and defaulting to **Test**. In Test mode every message goes to the test recipient with a "redirected while testing" banner. |

**Coming with ADO 5884 (not read yet; do not set until that ships):**
`EMAIL_BACKEND` (`outlook` / `sendgrid`), the SendGrid API key (**secret**),
and the from-address. It must be an address verified in SendGrid, because
SendGrid accepts mail from an unverified sender and then silently drops it.

### Sign-in (SSO)

Leave `CAPRI_ENABLE_SSO` unset until the Entra app registration exists (ADO
5881). Full detail: `docs/sso-support-runbook.md`.

| Variable | Required | Secret | Dev value | Notes |
|---|---|---|---|---|
| `CAPRI_ENABLE_SSO` | no | no | unset → later `1` | With `1` and all five values below present, SSO is the **only** way in: password login is refused. If this is `1` but any value is missing, SSO stays **off**, a startup warning says so, and password login keeps working. To recover from a bad setup, set it to `0` and restart. |
| `CAPRI_SSO_TENANT_ID` | with SSO | no | from IT | |
| `CAPRI_SSO_CLIENT_ID` | with SSO | no | from IT | CAPRI's own app registration, not ARIA's or APEX's. |
| `CAPRI_SSO_CLIENT_SECRET` | with SSO | **yes** | — | Has an expiry date. An expired secret is a total outage with no warning inside the app. |
| `CAPRI_SSO_REDIRECT_URI` | with SSO | no | `https://capri-dev.uniteduptime.com/api/auth/sso/callback` | Must match the registration **exactly**. |
| `CAPRI_SSO_ALLOWED_GROUPS` | with SSO | no | object ID of `SEC-App-Capri-Dev` | **Object IDs, not display names**, comma-separated. A group name here fails every sign-in with `not_in_group`. |

### Monitoring

| Variable | Required | Secret | Dev value | Notes |
|---|---|---|---|---|
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | no | **yes** | — | Application Insights. Unset, telemetry is off and nothing is sent. The SDK's own variable name (`backend/app/telemetry.py`). A malformed value stops the app from starting. |

### Do not set

- **`CAPRI_VERSION`** is baked into the image from the pipeline's build number
  (`--build-arg`) and shown in `/api/health`. Setting it on the Container App
  would hide which build is actually running.
- **`FLASK_DEBUG` / `FLASK_ENV`** must never be on in a deployed container.
  gunicorn serves the app, and nothing on the server needs Flask's debugger.

## How the container runs

- `flask db upgrade`, then gunicorn on port 8000 (`backend/gunicorn.conf.py`:
  2 workers × 4 threads). If a migration fails, the container never starts,
  and the pipeline reports an unhealthy revision.
- **One replica.** Every replica runs migrations at start, and two starting
  together would race. Multiple gunicorn **workers** are fine, because all
  sign-in state lives in the signed session cookie.
- Tests run inside the image build (pytest, vitest and the TypeScript check),
  so a failing test stops the pipeline before anything is deployed.
- No Docker is needed anywhere on our side (and IT does not allow it locally).
  `az acr build` builds the image in Azure Container Registry.

## Checking a deployment

Needs the VPN for Dev, and no sign-in:

```
curl -s https://capri-dev.uniteduptime.com/api/health
curl -s https://capri-dev.uniteduptime.com/api/auth/config
```

`/api/health` reports modes, never setting values:

| Field | Should be (Dev) | If not |
|---|---|---|
| `status` / `database` | `ok` (HTTP 200) | HTTP 503 means the database is unreachable: check the network path to the private endpoint and the SQL user. |
| `db_backend` | `mssql` | `sqlite` means neither database variable reached the container. On a deployed server the app should refuse to start in that case, so treat this as a bug. |
| `email_backend` | `off` until 5884, then `sendgrid` | `outlook` means `EMAIL_ENABLED=1` was set before the SendGrid backend exists. |
| `email_mode` | `test` until go-live | `live` means real recipients are being emailed. |
| `sso` | `off` until 5881, then `on` | `off` after enabling means `CAPRI_ENABLE_SSO` isn't `1` or one of the five values is missing. The startup log names which. |
| `telemetry` | `on` | `APPLICATIONINSIGHTS_CONNECTION_STRING` is unset. |
| `version` | the pipeline's build number | `dev` means the image wasn't built by the pipeline. |

## First deploy

1. The Dev database was **seeded on 2026-09-18**, so it already contains
   `admin@uniteduptime.com` with the public password `ChangeMe123!`. Deal with
   it in step 4, before anyone else can reach Dev.
2. Deploy with `EMAIL_ENABLED=0` and `CAPRI_ENABLE_SSO` unset. Check
   `/api/health` against the table above.
3. Create the real administrator from a console in the container
   (`az containerapp exec`). It prompts for a password of at least 12
   characters:
   ```
   python create_admin.py <email> "<name>"
   ```
   Never run `python seed.py` here. It refuses a non-SQLite database unless
   forced, because its admin password is public.
4. Sign in as the new admin and **deactivate `admin@uniteduptime.com`** under
   Admin → Users.
5. Set up divisions, regions (VP pools), approval thresholds and users. Decide
   whether the seed's sample divisions (100, 200) and the Central region stay.
6. Upload an attachment to a draft, redeploy, and confirm it still downloads.
   That proves `UPLOAD_ROOT` is on the file share.
7. Once 5884 ships: enable email **in Test mode**, walk one request through
   submit → L1 → L2 → L3 → finance, and check every email in classic Outlook,
   including the images and the record PDF.

## Rollback

Redeploy the previous image tag (`az containerapp update --image
<registry>/capri:<older build>`).

**Only roll back to an image with the same migration head.** Migrations are
Alembic, and the container runs `flask db upgrade` at start. An older image
does not know the newer revision recorded in the database, so it fails with
*"Can't locate revision"* and never starts. To go back across a migration,
first run `flask db downgrade <revision>` from the **newer** image's console,
then redeploy the older image.
