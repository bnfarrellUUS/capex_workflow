# CAPRI container image. Built in Azure by `az acr build` from
# pipelines/azure-pipelines-dev.yml -- nobody needs Docker installed locally
# (IT policy), and local development stays on run-app.ps1.
#
# Stages:
#   frontend  node: vitest, then `npm run build` (tsc typecheck + vite build)
#   base      python + Microsoft ODBC Driver 18 + requirements
#   test      base + backend pytest; the final stage copies its marker file,
#             so a failing test fails the build and nothing is deployed
#   final     base + backend + frontend/dist, served by gunicorn
#
# Layout mirrors the repo (/app/backend, /app/frontend/dist) because
# create_app() finds the SPA at <repo root>/frontend/dist.

FROM node:22-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx vitest run && npm run build


FROM python:3.14-slim AS base
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

# Microsoft's ODBC Driver 18, which pyodbc needs to reach Azure SQL. It is a
# system library, not a pip package, and its absence only surfaces at connect
# time inside the running container ("Data source name not found"). The Debian
# release is read from the base image so a base-image bump cannot pull the
# wrong repo. ACCEPT_EULA=Y is required by the package. (Same block as APEX.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl gnupg ca-certificates \
    && . /etc/os-release \
    && curl -fsSL -o /tmp/packages-microsoft-prod.deb \
       "https://packages.microsoft.com/config/debian/${VERSION_ID}/packages-microsoft-prod.deb" \
    && dpkg -i /tmp/packages-microsoft-prod.deb \
    && rm /tmp/packages-microsoft-prod.deb \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 unixodbc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


FROM base AS test
COPY backend/ ./
RUN python -m pytest -q && touch /tmp/tests-passed


FROM base AS final
# The pipeline passes its build number; /api/health reports it as `version`.
ARG CAPRI_VERSION=dev
ENV FLASK_APP=wsgi.py CAPRI_VERSION=$CAPRI_VERSION
COPY backend/ ./
COPY --from=frontend /app/frontend/dist /app/frontend/dist
COPY --from=test /tmp/tests-passed /tmp/tests-passed

# Fail the build, not the deployment, if the app cannot even be constructed.
RUN python -c "from app import create_app; create_app()"

# instance/ holds uploads when UPLOAD_ROOT is unset; on Azure, UPLOAD_ROOT
# points at a mounted file share instead (a container's own disk is wiped on
# every deploy).
RUN mkdir -p instance \
    && useradd --create-home --uid 10001 capri \
    && chown -R capri /app
USER capri

EXPOSE 8000

# Migrations run at start, before gunicorn: one replica, and the pipeline's
# health wait catches a failed upgrade as an unhealthy revision.
CMD ["sh", "-c", "flask db upgrade && exec gunicorn -c gunicorn.conf.py wsgi:app"]
