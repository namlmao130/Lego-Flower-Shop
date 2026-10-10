"""
Script migration: chạy 1 LẦN DUY NHẤT sau khi pull code có tính năng đăng nhập khách hàng.

Vì sao cần script này?
db.create_all() của SQLAlchemy chỉ tạo các BẢNG MỚI còn thiếu (ví dụ bảng `customers`),
nó KHÔNG tự động thêm CỘT MỚI vào bảng đã tồn tại sẵn (ví dụ cột `customer_id` trong
bảng `reviews` đã có từ trước). Nếu không chạy script này, app sẽ báo lỗi:
    sqlite3.OperationalError: no such column: reviews.customer_id

"""

import sqlite3
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from config import Config

DB_PATH = Config.SQLALCHEMY_DATABASE_URI.replace("sqlite:///", "")


def column_exists(cursor, table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def main():
    if not Config.SQLALCHEMY_DATABASE_URI.startswith("sqlite:///"):
        raise SystemExit(
            "Legacy SQLite migration only. PostgreSQL schema is created by web.py; transfer data with transfer_to_postgres.py before first startup."
        )
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    if not column_exists(cur, "reviews", "customer_id"):
        print("Đang thêm cột 'customer_id' vào bảng 'reviews'...")
        cur.execute("ALTER TABLE reviews ADD COLUMN customer_id INTEGER REFERENCES customers(id)")
        conn.commit()
        print("✅ Đã thêm cột customer_id.")
    else:
        print("Cột customer_id đã tồn tại, bỏ qua.")

    if not column_exists(cur, "customers", "email"):
        print("Đang thêm cột 'email' vào bảng 'customers'...")
        cur.execute("ALTER TABLE customers ADD COLUMN email VARCHAR(120)")
        conn.commit()
        print("✅ Đã thêm cột email.")
    else:
        print("Cột email đã tồn tại, bỏ qua.")

    if not column_exists(cur, "customers", "avatar"):
        print("Đang thêm cột 'avatar' vào bảng 'customers'...")
        cur.execute("ALTER TABLE customers ADD COLUMN avatar VARCHAR(255)")
        conn.commit()
        print("✅ Đã thêm cột avatar.")
    else:
        print("Cột avatar đã tồn tại, bỏ qua.")

    conn.close()

    # Tạo bảng customers nếu chưa có (bảng hoàn toàn mới nên db.create_all() xử lý được)
    from models import db
    from web import app

    with app.app_context():
        db.create_all()
    print("✅ Đã đảm bảo bảng 'customers' tồn tại.")
    print("\nMigration hoàn tất! Giờ bạn có thể chạy: python web.py")


if __name__ == "__main__":
    main()
