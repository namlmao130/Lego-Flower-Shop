"""Routes / cart."""

from flask import flash, jsonify, redirect, render_template, request, session, url_for

from app.models import Product
from app.services.cart_service import get_cart_details


def view_cart():
    """Xem trang giỏ hàng."""
    items, total_price, total_quantity = get_cart_details()
    return render_template(
        "cart.html", items=items, total_price=total_price, total_quantity=total_quantity
    )


def cart_add():
    """Thêm sản phẩm vào giỏ hàng."""
    data = request.get_json(silent=True) or request.form
    try:
        product_id = int(data.get("product_id")) if data.get("product_id") is not None else None
    except (ValueError, TypeError):
        product_id = None
    try:
        quantity = int(data.get("quantity", 1)) if data.get("quantity") is not None else 1
    except (ValueError, TypeError):
        quantity = 1
    buy_now = data.get("buy_now")

    if not product_id or quantity <= 0:
        if request.is_json:
            return jsonify({"success": False, "error": "Dữ liệu không hợp lệ"}), 400
        flash("Dữ liệu không hợp lệ", "error")
        return redirect(request.referrer or url_for("products"))

    product = Product.query.get_or_404(product_id)
    if product.stock <= 0:
        if request.is_json:
            return jsonify({"success": False, "error": "Sản phẩm này tạm thời hết hàng"}), 400
        flash(f'Sản phẩm "{product.name}" tạm thời hết hàng.', "warning")
        return redirect(request.referrer or url_for("products"))

    cart = session.get("cart", {})
    if not isinstance(cart, dict):
        cart = {}

    pid_str = str(product_id)
    current_qty = cart.get(pid_str, 0)
    new_qty = current_qty + quantity
    if new_qty > product.stock:
        new_qty = product.stock

    cart[pid_str] = new_qty
    session["cart"] = cart
    session.modified = True

    if buy_now:
        return redirect(url_for("checkout"))

    items, total_price, total_quantity = get_cart_details()

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(
            {
                "success": True,
                "cart_count": total_quantity,
                "message": f'Đã thêm {quantity} x "{product.name}" vào giỏ hàng!',
                "product_name": product.name,
                "product_price_str": f"{product.price:,.0f} đ",
                "thumbnail": url_for("static", filename="uploads/" + product.thumbnail)
                if product.thumbnail
                else None,
                "total_price": total_price,
                "total_price_str": f"{total_price:,.0f} đ",
            }
        )

    flash(f'Đã thêm "{product.name}" vào giỏ hàng!', "success")
    return redirect(request.referrer or url_for("view_cart"))


def cart_update():
    """Cập nhật số lượng sản phẩm trong giỏ hàng."""
    data = request.get_json(silent=True) or request.form
    try:
        product_id = int(data.get("product_id")) if data.get("product_id") is not None else None
    except (ValueError, TypeError):
        product_id = None
    try:
        quantity = int(data.get("quantity")) if data.get("quantity") is not None else 0
    except (ValueError, TypeError):
        quantity = 0

    if not product_id:
        return jsonify({"success": False, "error": "Thiếu ID sản phẩm"}), 400

    cart = session.get("cart", {})
    if not isinstance(cart, dict):
        cart = {}

    pid_str = str(product_id)
    product = Product.query.get(product_id)

    max_reached = False
    if quantity is None or quantity <= 0:
        cart.pop(pid_str, None)
    else:
        if product and quantity > product.stock:
            quantity = product.stock
            max_reached = True
        cart[pid_str] = quantity

    session["cart"] = cart
    session.modified = True

    items, total_price, total_quantity = get_cart_details()

    if request.is_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        item_subtotal = 0
        if product and pid_str in cart:
            item_subtotal = product.price * cart[pid_str]
        return jsonify(
            {
                "success": True,
                "cart_count": total_quantity,
                "item_subtotal": item_subtotal,
                "item_subtotal_str": f"{item_subtotal:,.0f} đ",
                "total_price": total_price,
                "total_price_str": f"{total_price:,.0f} đ",
                "total_quantity": total_quantity,
                "quantity": cart.get(pid_str, 0),
                "max_reached": max_reached,
                "available_stock": product.stock if product else 0,
            }
        )

    return redirect(url_for("view_cart"))


def cart_remove(product_id):
    """Xóa sản phẩm khỏi giỏ hàng."""
    cart = session.get("cart", {})
    if isinstance(cart, dict):
        cart.pop(str(product_id), None)
        session["cart"] = cart
        session.modified = True
    flash("Đã xóa sản phẩm khỏi giỏ hàng.", "info")
    return redirect(url_for("view_cart"))


def cart_clear():
    """Xóa toàn bộ giỏ hàng."""
    session.pop("cart", None)
    session.modified = True
    flash("Đã xóa toàn bộ giỏ hàng.", "info")
    return redirect(url_for("view_cart"))


def register_routes(app):
    """Register handlers, retaining the public endpoint names."""
    app.route("/cart")(view_cart)
    app.route("/cart/add", methods=["POST"])(cart_add)
    app.route("/cart/update", methods=["POST"])(cart_update)
    app.route("/cart/remove/<int:product_id>", methods=["POST"])(cart_remove)
    app.route("/cart/clear", methods=["POST"])(cart_clear)
