"""Routes / checkout."""

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user

from app.extensions import limiter
from app.models import Customer
from app.services.cart_service import get_cart_details
from app.services.order_service import StockUnavailable, place_order
from app.validators import PHONE_REGEX, normalize_phone


@limiter.limit("10 per minute")
def checkout():
    """Trang thanh toán / xác nhận đặt hàng."""
    items, total_price, total_quantity = get_cart_details()
    if not items or total_quantity == 0:
        flash("Giỏ hàng của bạn đang trống. Vui lòng chọn sản phẩm trước khi đặt hàng!", "warning")
        return redirect(url_for("products"))

    if request.method == "POST":
        customer_name = (request.form.get("customer_name") or "").strip()
        customer_phone = (request.form.get("customer_phone") or "").strip()
        shipping_address = (request.form.get("shipping_address") or "").strip()
        delivery_time = (request.form.get("delivery_time") or "Giao sớm nhất có thể").strip()
        customer_note = (request.form.get("customer_note") or "").strip()

        if not customer_name or not customer_phone or not shipping_address:
            flash("Vui lòng điền đầy đủ Họ tên, Số điện thoại và Địa chỉ nhận hàng!", "error")
            return render_template(
                "checkout.html", items=items, total_price=total_price, total_quantity=total_quantity
            )

        customer_phone = normalize_phone(customer_phone)
        if not PHONE_REGEX.match(customer_phone):
            flash(
                "Số điện thoại không hợp lệ. Vui lòng nhập số điện thoại 10 chữ số (VD: 0912345678).",
                "error",
            )
            return render_template(
                "checkout.html", items=items, total_price=total_price, total_quantity=total_quantity
            )

        # Kiểm tra tồn kho lần cuối
        for item in items:
            p = item["product"]
            qty = item["quantity"]
            if p.stock < qty:
                flash(
                    f'Sản phẩm "{p.name}" chỉ còn {p.stock} bó trong kho. Vui lòng giảm số lượng!',
                    "error",
                )
                return redirect(url_for("view_cart"))

        customer_id = None
        if current_user.is_authenticated and isinstance(current_user, Customer):
            customer_id = current_user.id

        try:
            order_code = place_order(
                items,
                total_price,
                customer_id=customer_id,
                customer_name=customer_name,
                customer_phone=customer_phone,
                shipping_address=shipping_address,
                delivery_time=delivery_time,
                customer_note=customer_note,
            )
        except StockUnavailable as error:
            flash(
                f'Rất tiếc, sản phẩm "{error.product_name}" vừa có người khác mua hết. '
                "Vui lòng kiểm tra lại giỏ hàng!",
                "error",
            )
            return redirect(url_for("view_cart"))

        session.pop("cart", None)
        session.modified = True

        return redirect(url_for("order_success", order_code=order_code))

    default_name = ""
    default_phone = ""
    if current_user.is_authenticated and isinstance(current_user, Customer):
        default_name = current_user.full_name or ""
        default_phone = current_user.phone or ""

    return render_template(
        "checkout.html",
        items=items,
        total_price=total_price,
        total_quantity=total_quantity,
        default_name=default_name,
        default_phone=default_phone,
    )


def register_routes(app):
    """Register handlers, retaining the public endpoint names."""
    app.route("/checkout", methods=["GET", "POST"])(checkout)
