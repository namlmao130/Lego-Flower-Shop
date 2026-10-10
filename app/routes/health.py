"""Read-only deployment readiness probe with no customer information."""

import os

from flask import current_app, jsonify
from sqlalchemy import text

from app.extensions import db


def health():
    try:
        db.session.execute(text("SELECT 1"))
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Database readiness check failed")
        return jsonify(status="unavailable"), 503
    return jsonify(status="ok", revision=os.environ.get("RENDER_GIT_COMMIT", "local")[:12])


def register_routes(app):
    app.add_url_rule("/health", view_func=health)
