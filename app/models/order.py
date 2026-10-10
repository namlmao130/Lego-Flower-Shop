"""Order database models. Existing table names are preserved."""

from datetime import datetime

from app.extensions import db


class Order(db.Model):
    """Đơn đặt hàng từ khách hàng."""

    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True, index=True)

    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False, index=True)
    shipping_address = db.Column(db.String(255), nullable=False)
    delivery_time = db.Column(
        db.String(100), nullable=True
    )  # Hẹn giờ giao hoa (VD: Giao sớm nhất / Hẹn ngày 20/10)
    customer_note = db.Column(db.Text, nullable=True)  # Ghi chú hoặc lời chúc viết thiệp
    cancel_reason = db.Column(db.String(255), nullable=True)  # Lý do hủy đơn nếu có

    total_price = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(
        db.String(20), nullable=False, default="pending", index=True
    )  # pending, confirmed, shipping, completed, cancelled
    payment_status = db.Column(
        db.String(30), nullable=False, default="contact_later"
    )  # contact_later, paid, unpaid
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    customer = db.relationship(
        "Customer", backref=db.backref("orders", lazy=True, order_by="Order.created_at.desc()")
    )
    items = db.relationship("OrderItem", backref="order", cascade="all, delete-orphan", lazy=True)

    __table_args__ = (db.Index("idx_orders_customer_created", "customer_id", "created_at"),)

    @property
    def status_label(self):
        labels = {
            "pending": "Chờ xác nhận",
            "confirmed": "Đã xác nhận",
            "shipping": "Đang giao hàng",
            "completed": "Hoàn thành",
            "cancelled": "Đã hủy",
        }
        return labels.get(self.status, self.status)

    @property
    def status_badge_class(self):
        classes = {
            "pending": "bg-warning text-dark",
            "confirmed": "bg-info text-dark",
            "shipping": "bg-primary text-white",
            "completed": "bg-success text-white",
            "cancelled": "bg-danger text-white",
        }
        return classes.get(self.status, "bg-secondary text-white")

    @property
    def step_number(self):
        steps = {"pending": 1, "confirmed": 2, "shipping": 3, "completed": 4, "cancelled": -1}
        return steps.get(self.status, 1)

    @property
    def can_cancel(self):
        return self.status == "pending"

    def __repr__(self):
        return f"<Order {self.order_code} - {self.total_price}đ>"


class OrderItem(db.Model):
    """Chi tiết từng sản phẩm trong đơn hàng."""

    __tablename__ = "order_items"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True, index=True)

    product_name = db.Column(db.String(200), nullable=False)
    product_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    subtotal = db.Column(db.Float, nullable=False)
    product_image = db.Column(db.String(255), nullable=True)

    product = db.relationship("Product", backref=db.backref("order_items", lazy=True))

    def __repr__(self):
        return f"<OrderItem {self.product_name} x{self.quantity}>"
