"""WSGI entry point: gunicorn web:app; python web.py for local development."""

from app import create_app
from app.extensions import cache, db, limiter

app = create_app()
__all__ = ["app", "create_app", "cache", "db", "limiter"]

if __name__ == "__main__":
    app.run(debug=True)
