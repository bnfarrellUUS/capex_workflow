from flask import Flask, jsonify

from .config import DevConfig
from .extensions import db, migrate, login_manager, csrf


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

    return app
