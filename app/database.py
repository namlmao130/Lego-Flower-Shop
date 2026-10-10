"""Database."""

import os

from flask import current_app as app
from sqlalchemy import event

from app.extensions import db
from app.models import Admin


def ensure_database_indexes():
    """Tự động đảm bảo tất cả chỉ mục (indexes) tối ưu hiệu năng tồn tại mà không làm thay đổi hay mất dữ liệu."""
    try:
        with db.engine.connect() as conn:
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_products_category_id_desc ON products(category_id, id DESC)",
                "CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id_id ON chat_messages(session_id, id ASC)",
                "CREATE INDEX IF NOT EXISTS idx_chat_messages_unread_badge ON chat_messages(sender_type, is_read)",
                "CREATE INDEX IF NOT EXISTS idx_orders_customer_created ON orders(customer_id, created_at DESC)",
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_customers_email ON customers(email) WHERE email IS NOT NULL",
            ]
            for idx_sql in indexes:
                conn.execute(db.text(idx_sql))
            if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
                conn.execute(db.text("PRAGMA optimize"))
            conn.commit()
    except Exception:
        pass


def create_default_admin():
    """Tạo sẵn 1 tài khoản admin nếu chưa có, để bạn login lần đầu."""
    if not Admin.query.filter_by(username="admin").first():
        admin = Admin(username="admin")
        password = os.environ.get("ADMIN_PASSWORD", "")
        if not password and db.engine.dialect.name == "postgresql":
            raise RuntimeError("Set ADMIN_PASSWORD before initializing a new PostgreSQL database.")
        admin.set_password(password or "admin123")
        db.session.add(admin)
        db.session.commit()
        print(">>> Đã tạo tài khoản admin: username=admin")


def configure_sqlite(app):
    """Install SQLite connection pragmas once for this engine."""
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite"):
        with app.app_context():

            @event.listens_for(db.engine, "connect")
            def _set_sqlite_pragma(dbapi_connection, connection_record):
                from app.services.search_service import normalize_search

                dbapi_connection.create_function(
                    "shop_search_normalize", 1, normalize_search, deterministic=True
                )
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute("PRAGMA cache_size=-64000")
                cursor.execute("PRAGMA mmap_size=268435456")
                cursor.execute("PRAGMA temp_store=MEMORY")
                cursor.execute("PRAGMA busy_timeout=15000")
                cursor.close()


def initialize_database():
    """Bootstrap schema with the same PostgreSQL advisory lock as before."""
    if db.engine.dialect.name == "postgresql":
        # Serialize schema/bootstrap across Gunicorn workers on first startup.
        with db.engine.connect() as bootstrap_connection:
            bootstrap_connection.execute(db.text("SELECT pg_advisory_lock(72024001)"))
            try:
                db.create_all()
                ensure_database_indexes()
                create_default_admin()
            finally:
                bootstrap_connection.execute(db.text("SELECT pg_advisory_unlock(72024001)"))
    else:
        db.create_all()
        ensure_database_indexes()
        create_default_admin()
