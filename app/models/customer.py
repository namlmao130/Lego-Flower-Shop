"""Customer database models. Existing table names are preserved."""

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class Customer(UserMixin, db.Model):
    """Tài khoản khách hàng, đăng nhập bằng số điện thoại hoặc email + mật khẩu (tách biệt với Admin)."""

    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True, index=True)
    full_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    avatar = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def short_name(self):
        """Lấy tên gọi ngắn gọn (từ cuối cùng của họ tên, VD: 'Nguyễn Văn Nam' -> 'Nam')"""
        if not self.full_name:
            return ""
        parts = self.full_name.strip().split()
        return parts[-1] if parts else self.full_name

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        # Tiền tố "customer-" để phân biệt với Admin trong cùng 1 Flask-Login session
        return f"customer-{self.id}"

    def __repr__(self):
        return f"<Customer {self.phone}>"
