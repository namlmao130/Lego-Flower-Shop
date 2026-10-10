"""Application factory. Importing the package never opens the database."""

import os
from pathlib import Path

from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix

from .extensions import cache, compress, db, limiter, login_manager


def create_app(config_overrides=None, *, initialize_database=True):
    """Create an app; tests can override config before extensions connect."""
    from config import Config

    from . import context, database, errors, security
    from .routes import register_routes

    # Keep deployed media paths and all template/static URLs unchanged.
    project_root = Path(__file__).resolve().parent.parent
    app = Flask(
        __name__, root_path=str(project_root), template_folder="templates", static_folder="static"
    )
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)
    if str(app.config.get("TRUST_PROXY", os.environ.get("TRUST_PROXY", "false"))).lower() == "true":
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    compress.init_app(app)
    cache.init_app(app)
    limiter.init_app(app)
    db.init_app(app)
    login_manager.init_app(app)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(
        app.config.get(
            "AVATAR_UPLOAD_FOLDER", os.path.join(app.config["UPLOAD_FOLDER"], "avatars")
        ),
        exist_ok=True,
    )
    security.register(app)
    context.register(app)
    errors.register(app)
    register_routes(app)
    database.configure_sqlite(app)
    if initialize_database:
        with app.app_context():
            database.initialize_database()
    return app
