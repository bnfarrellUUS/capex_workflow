import os

from flask import Flask, jsonify, send_from_directory, abort
from pydantic import ValidationError

from .config import DevConfig
from .extensions import db, migrate, login_manager, csrf
from .services.errors import ServiceError


def create_app(config_object=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object or DevConfig)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

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

    from .blueprints.thresholds import bp as thresholds_bp
    app.register_blueprint(thresholds_bp)

    from .blueprints.profile import bp as profile_bp
    app.register_blueprint(profile_bp)

    from .blueprints.requests import bp as requests_bp
    app.register_blueprint(requests_bp)

    from .blueprints.email_templates import bp as email_templates_bp
    app.register_blueprint(email_templates_bp)

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
