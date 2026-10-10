"""Services / cart service."""

from flask import session
from sqlalchemy.orm import selectinload

from app.models import Product


def get_cart_details():
    """Lấy danh sách sản phẩm, tổng tiền và tổng số lượng từ session cart (truy vấn 1 lần duy nhất)."""
    cart = session.get("cart", {})
    items = []
    total_price = 0
    total_quantity = 0

    if not isinstance(cart, dict):
        cart = {}

    to_remove = []
    pids = []
    valid_entries = []
    for pid_str, qty in list(cart.items()):
        try:
            pid = int(pid_str)
            qty = int(qty)
            if qty > 0:
                pids.append(pid)
                valid_entries.append((pid_str, pid, qty))
            else:
                to_remove.append(pid_str)
        except (ValueError, TypeError):
            to_remove.append(pid_str)

    products_by_id = {}
    if pids:
        prods = (
            Product.query.options(selectinload(Product.media)).filter(Product.id.in_(pids)).all()
        )
        products_by_id = {p.id: p for p in prods}

    for pid_str, pid, qty in valid_entries:
        product = products_by_id.get(pid)
        if not product:
            to_remove.append(pid_str)
            continue
        subtotal = product.price * qty
        total_price += subtotal
        total_quantity += qty
        items.append(
            {
                "product": product,
                "quantity": qty,
                "subtotal": subtotal,
                "in_stock": product.stock >= qty,
                "available_stock": product.stock,
            }
        )

    if to_remove:
        for r in to_remove:
            cart.pop(r, None)
        session["cart"] = cart
        session.modified = True

    return items, total_price, total_quantity
