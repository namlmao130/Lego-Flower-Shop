"""Routes / orders."""

from flask import flash, redirect, render_template, request, session, url_for
from flask_login import current_user
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.extensions import db, limiter
from app.models import Customer, Order
from app.validators import PHONE_REGEX, normalize_phone


def order_success(order_code):
    """Trang thông báo đặt hàng thành công."""
    order = Order.query.filter_by(order_code=order_code).first_or_404()
    return render_template("order_success.html", order=order)


def my_orders_view():
    """Trang xem & tra cứu đơn hàng của bạn (dành cho cả khách đã đăng nhập và khách vãng lai)."""
    search_query = ""
    status_filter = request.args.get("status", "").strip()

    if current_user.is_authenticated and isinstance(current_user, Customer):
        # Khách đã đăng nhập: hiển thị toàn bộ đơn hàng của tài khoản
        query = Order.query.filter_by(customer_id=current_user.id).options(
            selectinload(Order.items)
        )
        if status_filter:
            query = query.filter_by(status=status_filter)
        q = request.args.get("q", "").strip()
        if q:
            search_query = q
            query = query.filter(Order.order_code.ilike(f"%{q}%"))
        orders = query.order_by(Order.created_at.desc()).all()
        lookup_mode = "account"
    else:
        # Khách vãng lai / chưa đăng nhập: tra cứu qua SĐT hoặc mã đơn
        lookup_mode = "guest"
        orders = []
        identifier = ""
        if request.method == "POST":
            identifier = request.form.get("identifier", "").strip()
        else:
            identifier = request.args.get("identifier", "").strip()

        if identifier:
            search_query = identifier
            norm_phone = normalize_phone(identifier)

            # Nếu nhập đúng mã đơn hàng, chuyển thẳng tới trang chi tiết theo dõi
            if identifier.upper().startswith("LF"):
                exact_order = Order.query.filter(
                    func.upper(Order.order_code) == identifier.upper()
                ).first()
                if exact_order:
                    return redirect(url_for("order_detail", order_code=exact_order.order_code))

            query = Order.query.options(selectinload(Order.items))
            if norm_phone and PHONE_REGEX.match(norm_phone):
                query = query.filter(Order.customer_phone == norm_phone)
            else:
                query = query.filter(
                    (Order.order_code.ilike(f"%{identifier}%"))
                    | (Order.customer_phone == identifier)
                )

            if status_filter:
                query = query.filter_by(status=status_filter)
            orders = query.order_by(Order.created_at.desc()).all()
            if not orders:
                flash(
                    f'Không tìm thấy đơn hàng nào khớp với thông tin "{identifier}". Vui lòng kiểm tra lại Số điện thoại hoặc Mã đơn hàng!',
                    "warning",
                )

    return render_template(
        "orders.html",
        orders=orders,
        status_filter=status_filter,
        search_query=search_query,
        lookup_mode=lookup_mode,
    )


def order_detail(order_code):
    """Trang chi tiết & theo dõi tiến trình đơn hàng."""
    order = (
        Order.query.options(selectinload(Order.items))
        .filter_by(order_code=order_code)
        .first_or_404()
    )
    return render_template("order_detail.html", order=order)


@limiter.limit("10 per minute")
def order_cancel_customer(order_code):
    """Khách hàng tự hủy đơn hàng khi đơn còn ở trạng thái Chờ xác nhận."""
    order = Order.query.filter_by(order_code=order_code).first_or_404()
    if not order.can_cancel:
        flash(
            "Đơn hàng đã được xác nhận hoặc đang giao nên không thể tự hủy trực tiếp. Vui lòng liên hệ shop qua Zalo/Hotline để được hỗ trợ!",
            "warning",
        )
        return redirect(request.referrer or url_for("order_detail", order_code=order_code))

    cancel_reason = (
        request.form.get("cancel_reason") or "Khách hàng yêu cầu hủy đơn qua website"
    ).strip()
    order.status = "cancelled"
    order.cancel_reason = cancel_reason

    # Hoàn lại số lượng tồn kho
    for item in order.items:
        if item.product:
            item.product.stock += item.quantity

    db.session.commit()
    flash(
        f"Đã hủy thành công đơn hàng #{order.order_code}. Số lượng hoa đã được hoàn trả lại kho.",
        "success",
    )
    return redirect(request.referrer or url_for("order_detail", order_code=order_code))


@limiter.limit("15 per minute")
def order_reorder(order_code):
    """Mua lại / Đặt lại toàn bộ sản phẩm của đơn hàng cũ vào giỏ."""
    order = (
        Order.query.options(selectinload(Order.items))
        .filter_by(order_code=order_code)
        .first_or_404()
    )
    cart = session.get("cart", {})
    if not isinstance(cart, dict):
        cart = {}

    added_count = 0
    for item in order.items:
        if item.product and item.product.stock > 0:
            pid_str = str(item.product.id)
            current_qty = cart.get(pid_str, 0)
            new_qty = min(current_qty + item.quantity, item.product.stock)
            cart[pid_str] = new_qty
            added_count += 1

    session["cart"] = cart
    session.modified = True

    if added_count > 0:
        flash(f"Đã thêm các món từ đơn #{order.order_code} vào giỏ hàng của bạn!", "success")
    else:
        flash("Rất tiếc, các mẫu hoa trong đơn này hiện đang tạm hết hàng.", "warning")

    return redirect(url_for("view_cart"))


def register_routes(app):
    """Register handlers, retaining the public endpoint names."""
    app.route("/order-success/<order_code>")(order_success)
    app.route("/orders", methods=["GET", "POST"])(my_orders_view)
    app.route("/order/<order_code>")(order_detail)
    app.route("/order/<order_code>/cancel", methods=["POST"])(order_cancel_customer)
    app.route("/order/<order_code>/reorder", methods=["POST"])(order_reorder)
