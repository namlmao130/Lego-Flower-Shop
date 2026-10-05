import re
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# Số điện thoại di động VN chuẩn: đúng 10 chữ số bắt đầu bằng 03, 05, 07, 08, 09 (hoặc +84 theo sau 9 số)
PHONE_REGEX = re.compile(r'^(0|\+84)[35789]\d{8}$')
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')


def normalize_phone(raw_phone):
    """Chuẩn hóa số điện thoại: bỏ khoảng trắng/dấu gạch, chuyển +84 thành 0 để lưu thống nhất."""
    if not raw_phone:
        return ''
    cleaned = re.sub(r'[\s\-.]', '', raw_phone.strip())
    if cleaned.startswith('+84'):
        cleaned = '0' + cleaned[3:]
    elif cleaned.startswith('84') and len(cleaned) == 11 and cleaned[2] in '35789':
        cleaned = '0' + cleaned[2:]
    return cleaned


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
    """Tài khoản khách hàng, đăng nhập bằng số điện thoại hoặc email + mật khẩu (tách biệt với Admin)."""
    __tablename__ = 'customers'

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


class ChatMessage(db.Model):
    """Tin nhắn chat giữa khách hàng và Admin / Shop."""
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)
    sender_type = db.Column(db.String(20), nullable=False)  # 'customer' hoặc 'admin'
    sender_name = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    is_read = db.Column(db.Boolean, default=False)

    customer = db.relationship('Customer', backref=db.backref('chat_messages', lazy=True))

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'customer_id': self.customer_id,
            'sender_type': self.sender_type,
            'sender_name': self.sender_name,
            'message': self.message,
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'time_str': self.created_at.strftime('%H:%M'),
            'is_read': self.is_read
        }

    def __repr__(self):
        return f'<ChatMessage {self.id} from {self.sender_type} ({self.sender_name})>'


class Order(db.Model):
    """Đơn đặt hàng từ khách hàng."""
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customers.id'), nullable=True)

    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    shipping_address = db.Column(db.String(255), nullable=False)
    customer_note = db.Column(db.Text, nullable=True)  # Ghi chú hoặc lời chúc viết thiệp

    total_price = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, confirmed, shipping, completed, cancelled
    payment_status = db.Column(db.String(30), nullable=False, default='contact_later')  # contact_later, paid, unpaid
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship('Customer', backref=db.backref('orders', lazy=True, order_by='Order.created_at.desc()'))
    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan', lazy=True)

    @property
    def status_label(self):
        labels = {
            'pending': 'Chờ xác nhận',
            'confirmed': 'Đã xác nhận',
            'shipping': 'Đang giao hàng',
            'completed': 'Hoàn thành',
            'cancelled': 'Đã hủy'
        }
        return labels.get(self.status, self.status)

    @property
    def status_badge_class(self):
        classes = {
            'pending': 'bg-warning text-dark',
            'confirmed': 'bg-info text-dark',
            'shipping': 'bg-primary text-white',
            'completed': 'bg-success text-white',
            'cancelled': 'bg-danger text-white'
        }
        return classes.get(self.status, 'bg-secondary text-white')

    def __repr__(self):
        return f'<Order {self.order_code} - {self.total_price}đ>'


class OrderItem(db.Model):
    """Chi tiết từng sản phẩm trong đơn hàng."""
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)

    product_name = db.Column(db.String(200), nullable=False)
    product_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    subtotal = db.Column(db.Float, nullable=False)
    product_image = db.Column(db.String(255), nullable=True)

    product = db.relationship('Product', backref=db.backref('order_items', lazy=True))

    def __repr__(self):
        return f'<OrderItem {self.product_name} x{self.quantity}>'
