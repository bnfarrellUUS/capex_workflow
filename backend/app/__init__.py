import os

from flask import Flask, jsonify, send_from_directory, abort, request, session
from pydantic import ValidationError

from .config import INSECURE_DEV_SECRET, config_from_env, is_local_url
from .extensions import db, migrate, login_manager, csrf
from .services.errors import ServiceError


def _refuse_unsafe_deployment(config):
    """A deployed server (non-local APP_BASE_URL) must have its own SECRET_KEY
    and be served over https. Failing here names the problem in the container
    log; the alternatives are forgeable sessions (the dev key is in the repo)
    or secure-only cookies that browsers never send over http, which looks like
    every sign-in silently failing."""
    base_url = config.get("APP_BASE_URL")
    if is_local_url(base_url):
        return
    if config.get("SECRET_KEY") in (None, "", INSECURE_DEV_SECRET):
        raise RuntimeError(
            f"SECRET_KEY must be set to a random value when APP_BASE_URL is "
            f"{base_url!r}; refusing to start with the development key.")
    if not base_url.startswith("https://"):
        raise RuntimeError(
            f"APP_BASE_URL must be https:// on a deployed server (got "
            f"{base_url!r}): session cookies are secure-only there.")
    if not config.get("UPLOAD_ROOT"):
        # The default (instance/uploads) is the container's own disk, wiped on
        # every deploy while the database keeps pointing at the files.
        raise RuntimeError(
            "UPLOAD_ROOT must point at persistent storage (a mounted file share) "
            "on a deployed server.")


def _refuse_incomplete_email(config):
    """An unknown sender name, or SendGrid switched on without its key or a
    from-address, would otherwise fail on every send -- logged, never shown to
    a user, and (for a bad from-address) not even an error at SendGrid."""
    backend = config.get("EMAIL_BACKEND") or "outlook"
    if backend not in ("outlook", "sendgrid"):
        raise RuntimeError(
            f"EMAIL_BACKEND must be 'outlook' or 'sendgrid' (got {backend!r}).")
    if (backend == "outlook" and config.get("EMAIL_ENABLED")
            and not is_local_url(config.get("APP_BASE_URL"))):
        # Outlook is a Windows desktop app driven over COM; on a server every
        # send would fail inside notify and only be logged.
        raise RuntimeError(
            "EMAIL_BACKEND must be 'sendgrid' when EMAIL_ENABLED=1 on a deployed "
            "server; the Outlook backend only works on a Windows PC.")
    if backend == "sendgrid" and config.get("EMAIL_ENABLED"):
        for key in ("SENDGRID_API_KEY", "EMAIL_FROM"):
            if not config.get(key):
                raise RuntimeError(
                    f"{key} must be set when EMAIL_ENABLED=1 and EMAIL_BACKEND=sendgrid.")


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or config_from_env())
    _refuse_unsafe_deployment(app.config)
    _refuse_incomplete_email(app.config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from . import telemetry
    app.config["CAPRI_TELEMETRY"] = telemetry.init_app(app)

    # Fail open on the flag: CAPRI_ENABLE_SSO=1 with a half-filled config
    # behaves as SSO-off so a typo cannot lock every user out of a working app.
    # Log it, so the mistake is visible rather than silent.
    if os.environ.get("CAPRI_ENABLE_SSO", "").strip() == "1":
        from app.services.sso_service import sso_config
        if sso_config() is None:
            app.logger.warning(
                "CAPRI_ENABLE_SSO=1 but the SSO configuration is incomplete - "
                "SSO is DISABLED and password login remains active. Check "
                "CAPRI_SSO_TENANT_ID, _CLIENT_ID, _CLIENT_SECRET, "
                "_ALLOWED_GROUPS and _REDIRECT_URI.")

    # A user flagged must_change_password may only hit the endpoints needed
    # to set a new password (or leave); everything else on the API is 403.
    exempt = {"auth.set_password", "auth.me", "auth.csrf_token", "auth.logout", "auth.login"}

    @app.before_request
    def _require_password_change():
        from flask_login import current_user
        if (request.blueprint is not None
                and current_user.is_authenticated
                and current_user.must_change_password
                # An SSO session has no password to change, so gating it would
                # lock the user out of everything with no form to escape
                # through. The flag stays on the row, so it still applies if
                # CAPRI_ENABLE_SSO is ever set back to 0.
                and session.get("auth_method") != "sso"
                and request.endpoint not in exempt):
            return jsonify(error="You must set a new password before continuing.",
                           code="PASSWORD_CHANGE_REQUIRED"), 403

    @login_manager.user_loader
    def load_user(user_id):
        from app.models import User
        return db.session.get(User, user_id)

    @login_manager.unauthorized_handler
    def unauthorized():
        return jsonify(error="Authentication required."), 401

    # Import models so their tables register on the metadata.
    from app import models  # noqa: F401

    from .blueprints.health import bp as health_bp
    app.register_blueprint(health_bp)

    from .blueprints.auth import bp as auth_bp
    app.register_blueprint(auth_bp)

    from .blueprints.users import bp as users_bp
    app.register_blueprint(users_bp)

    from .blueprints.divisions import bp as divisions_bp
    app.register_blueprint(divisions_bp)

    from .blueprints.regions import bp as regions_bp
    app.register_blueprint(regions_bp)

    from .blueprints.thresholds import bp as thresholds_bp
    app.register_blueprint(thresholds_bp)

    from .blueprints.profile import bp as profile_bp
    app.register_blueprint(profile_bp)

    from .blueprints.requests import bp as requests_bp
    app.register_blueprint(requests_bp)

    from .blueprints.email_templates import bp as email_templates_bp
    app.register_blueprint(email_templates_bp)

    from .blueprints.reports import bp as reports_bp
    app.register_blueprint(reports_bp)

    from .blueprints.request_sections import bp as request_sections_bp
    app.register_blueprint(request_sections_bp)

    from .blueprints.pings import bp as pings_bp
    app.register_blueprint(pings_bp)

    @app.errorhandler(ServiceError)
    def _handle_service_error(err: ServiceError):
        return jsonify(error=err.message), err.status

    @app.errorhandler(ValidationError)
    def _handle_validation_error(err: ValidationError):
        return jsonify(error="Validation failed.", details=err.errors()), 400

    # Serve the built React SPA from the same server as the API. `frontend/dist`
    # is produced by `vite build`; FRONTEND_DIST overrides the location in prod.
    repo_root = os.path.dirname(os.path.dirname(app.root_path))
    dist = app.config.get("FRONTEND_DIST") or os.path.join(repo_root, "frontend", "dist")

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_spa(path):
        # /api/* is owned by the blueprints; anything unmatched there is a real
        # 404, not the SPA shell.
        if path.startswith("api/"):
            abort(404)
        target = os.path.join(dist, path)
        if path and os.path.isfile(target):
            return send_from_directory(dist, path)
        index = os.path.join(dist, "index.html")
        if os.path.isfile(index):
            return send_from_directory(dist, "index.html")
        # dist not built (e.g. API-only/test runs): nothing to serve here.
        abort(404)

    return app
