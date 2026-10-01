import re
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Số điện thoại VN: bắt đầu bằng 0 hoặc +84, theo sau là 9-10 chữ số
PHONE_REGEX = re.compile(r'^(0|\+84)\d{9,10}$')


def normalize_phone(raw_phone):
    """Chuẩn hóa số điện thoại: bỏ khoảng trắng/dấu gạch, dùng để so sánh & lưu thống nhất."""
    if not raw_phone:
        return ''
    return re.sub(r'[\s\-.]', '', raw_phone.strip())


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    # Một category có nhiều product
    products = db.relationship('Product', backref='category', lazy=True)

    def __repr__(self):
        return f'<Category {self.name}>'


class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(200), nullable=True)  # ảnh cũ (giữ để tương thích ngược)
    stock = db.Column(db.Integer, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)

    @property
    def thumbnail(self):
        """Ảnh đại diện dùng cho trang chủ/danh sách: ưu tiên ảnh đầu tiên trong media"""
        for m in self.media:
            if m.media_type == 'image':
                return m.filename
        return self.image

    @property
    def average_rating(self):
        """Điểm đánh giá trung bình (0 nếu chưa có review nào)."""
        reviews = self.reviews
        if not reviews:
            return 0
        return round(sum(r.rating for r in reviews) / len(reviews), 1)

    @property
    def review_count(self):
        return len(self.reviews)

    def __repr__(self):
        return f'<Product {self.name}>'


class ProductMedia(db.Model):
    """Nhiều ảnh/video cho 1 sản phẩm, hiển thị dạng carousel ở trang chi tiết."""
    __tablename__ = 'product_media'
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    media_type = db.Column(db.String(10), nullable=False, default='image')  # 'image' hoặc 'video'

    product = db.relationship(
        'Product',
        backref=db.backref('media', cascade='all, delete-orphan', order_by='ProductMedia.id')
    )


class Review(db.Model):
    """Đánh giá của khách hàng cho 1 sản phẩm. Không yêu cầu đăng nhập (khách nhập tên)."""
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    # customer_id: NULL nếu là khách vãng lai gửi review không đăng nhập (giữ tương thích ngược)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    customer_name = db.Column(db.String(100), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1 đến 5 sao
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship(
        'Product',
        backref=db.backref('reviews', cascade='all, delete-orphan', order_by='Review.created_at.desc()')
    )
    customer = db.relationship('Customer', backref=db.backref('reviews', lazy=True))

    # Mỗi tài khoản khách hàng chỉ được đánh giá 1 sản phẩm 1 lần (không áp dụng cho khách vãng lai - customer_id NULL)
    __table_args__ = (
        db.UniqueConstraint('customer_id', 'product_id', name='uq_customer_product_review'),
    )

    def __repr__(self):
        return f'<Review {self.rating}★ by {self.customer_name} for product {self.product_id}>'


class Customer(UserMixin, db.Model):
    """Tài khoản khách hàng, đăng nhập bằng số điện thoại + mật khẩu (tách biệt với Admin)."""
    __tablename__ = 'customers'

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    full_name = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def short_name(self):
        """Lấy tên gọi ngắn gọn (từ cuối cùng của họ tên, VD: 'Nguyễn Văn Nam' -> 'Nam')"""
        if not self.full_name:
            return ''
        parts = self.full_name.strip().split()
        return parts[-1] if parts else self.full_name

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        # Tiền tố "customer-" để phân biệt với Admin trong cùng 1 Flask-Login session
        return f'customer-{self.id}'

    def __repr__(self):
        return f'<Customer {self.phone}>'


class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        # Tiền tố "admin-" để phân biệt với Customer trong cùng 1 Flask-Login session
        return f'admin-{self.id}'
