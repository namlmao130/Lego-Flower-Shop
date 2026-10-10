"""Services / order service."""

import uuid
from datetime import datetime

from app.extensions import db
from app.models import Order, OrderItem, Product


def generate_order_code():
    """Tạo mã đơn hàng dạng LF + NămThángNgày + 4 ký tự ngẫu nhiên (VD: LF261002A1B2)"""
    now_str = datetime.now().strftime("%y%m%d")
    rand_str = uuid.uuid4().hex[:4].upper()
    return f"LF{now_str}{rand_str}"


class StockUnavailable(Exception):
    """Another checkout consumed the requested stock before this transaction."""

    def __init__(self, product_name):
        self.product_name = product_name
        super().__init__(product_name)


def place_order(
    items,
    total_price,
    *,
    customer_id,
    customer_name,
    customer_phone,
    shipping_address,
    delivery_time,
    customer_note,
):
    """Create the order and reserve stock in one transaction.

    The caller validates form input; this service owns commit/rollback. It does
    not access HTTP requests or sessions, so it can be tested independently.
    """
    try:
        order_code = generate_order_code()
        while Order.query.filter_by(order_code=order_code).first():
            order_code = generate_order_code()
        order = Order(
            order_code=order_code,
            customer_id=customer_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            shipping_address=shipping_address,
            delivery_time=delivery_time,
            customer_note=customer_note,
            total_price=total_price,
            status="pending",
            payment_status="contact_later",
        )
        db.session.add(order)
        db.session.flush()
        for item in items:
            product = item["product"]
            quantity = item["quantity"]
            updated = (
                db.session.query(Product)
                .filter(
                    Product.id == product.id,
                    Product.stock >= quantity,
                )
                .update({Product.stock: Product.stock - quantity}, synchronize_session=False)
            )
            if updated != 1:
                raise StockUnavailable(product.name)
            db.session.add(
                OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    product_name=product.name,
                    product_price=product.price,
                    quantity=quantity,
                    subtotal=item["subtotal"],
                    product_image=product.thumbnail,
                )
            )
        db.session.commit()
        return order_code
    except Exception:
        db.session.rollback()
        raise
