"""Product database models. Existing table names are preserved."""

from app.extensions import db


class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)

    # Một category có nhiều product
    products = db.relationship("Product", backref="category", lazy=True)

    def __repr__(self):
        return f"<Category {self.name}>"


class Product(db.Model):
    __tablename__ = "products"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    image = db.Column(db.String(200), nullable=True)  # ảnh cũ (giữ để tương thích ngược)
    stock = db.Column(db.Integer, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)

    __table_args__ = (db.Index("idx_products_category_id_desc", "category_id", "id"),)

    @property
    def thumbnail(self):
        """Ảnh đại diện dùng cho trang chủ/danh sách: ưu tiên ảnh đầu tiên trong media"""
        for m in self.media:
            if m.media_type == "image":
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
        return f"<Product {self.name}>"


class ProductMedia(db.Model):
    """Nhiều ảnh/video cho 1 sản phẩm, hiển thị dạng carousel ở trang chi tiết."""

    __tablename__ = "product_media"
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    filename = db.Column(db.String(255), nullable=False)
    media_type = db.Column(db.String(10), nullable=False, default="image")  # 'image' hoặc 'video'

    product = db.relationship(
        "Product",
        backref=db.backref("media", cascade="all, delete-orphan", order_by="ProductMedia.id"),
    )
