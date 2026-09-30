from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


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


class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
