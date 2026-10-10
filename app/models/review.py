"""Review database models. Existing table names are preserved."""

from datetime import datetime

from app.extensions import db


class Review(db.Model):
    """Đánh giá của khách hàng cho 1 sản phẩm. Không yêu cầu đăng nhập (khách nhập tên)."""

    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False, index=True)
    # customer_id: NULL nếu là khách vãng lai gửi review không đăng nhập (giữ tương thích ngược)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True, index=True)
    customer_name = db.Column(db.String(100), nullable=False)
    rating = db.Column(db.Integer, nullable=False)  # 1 đến 5 sao
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship(
        "Product",
        backref=db.backref(
            "reviews", cascade="all, delete-orphan", order_by="Review.created_at.desc()"
        ),
    )
    customer = db.relationship("Customer", backref=db.backref("reviews", lazy=True))

    # Mỗi tài khoản khách hàng chỉ được đánh giá 1 sản phẩm 1 lần (không áp dụng cho khách vãng lai - customer_id NULL)
    __table_args__ = (
        db.UniqueConstraint("customer_id", "product_id", name="uq_customer_product_review"),
    )

    def __repr__(self):
        return f"<Review {self.rating}★ by {self.customer_name} for product {self.product_id}>"
