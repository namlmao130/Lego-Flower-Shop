"""Routes / admin orders."""

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import Order, OrderItem, Product
from app.security import admin_required

VALID_ORDER_STATUSES = {"pending", "confirmed", "shipping", "completed", "cancelled"}


def _set_order_status(order, new_status):
    """Change status while keeping product stock consistent."""
    old_status = order.status
    if new_status == old_status:
        return
    order.status = new_status
    if new_status == "cancelled" and old_status != "cancelled":
        for item in order.items:
            if item.product:
                item.product.stock += item.quantity
    elif old_status == "cancelled" and new_status != "cancelled":
        for item in order.items:
            if item.product:
                item.product.stock = max(0, item.product.stock - item.quantity)


def _restore_stock_before_delete(order):
    if order.status not in ("completed", "cancelled"):
        for item in order.items:
            if item.product:
                item.product.stock += item.quantity


@admin_required
def admin_orders():
    """Trang quản lý đơn hàng của Admin."""
    status_filter = request.args.get("status", "").strip()
    q = request.args.get("q", "").strip()

    query = Order.query.options(
        selectinload(Order.customer),
        selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.media),
    )
    if status_filter:
        query = query.filter(Order.status == status_filter)
    if q:
        search_pat = f"%{q}%"
        query = query.filter(
            (Order.order_code.ilike(search_pat))
            | (Order.customer_name.ilike(search_pat))
            | (Order.customer_phone.ilike(search_pat))
        )

    orders = query.order_by(Order.created_at.desc()).all()

    # Tối ưu: thay vì 6 câu COUNT riêng (tốn 6 query DB), chỉ dùng 1 câu GROUP BY
    status_counts = (
        db.session.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    )
    status_count_map = {s: c for s, c in status_counts}
    counts = {
        "all": sum(status_count_map.values()),
        "pending": status_count_map.get("pending", 0),
        "confirmed": status_count_map.get("confirmed", 0),
        "shipping": status_count_map.get("shipping", 0),
        "completed": status_count_map.get("completed", 0),
        "cancelled": status_count_map.get("cancelled", 0),
    }

    return render_template(
        "admin/orders.html", orders=orders, status_filter=status_filter, q=q, counts=counts
    )


@admin_required
def admin_order_update_status(order_id):
    """Admin cập nhật trạng thái đơn hàng."""
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get("status")
    if new_status in VALID_ORDER_STATUSES:
        _set_order_status(order, new_status)
        db.session.commit()
        flash(
            f'Đã cập nhật trạng thái đơn #{order.order_code} thành "{order.status_label}"!',
            "success",
        )
    return redirect(url_for("admin_orders"))


@admin_required
def admin_order_delete(order_id):
    """Admin xóa đơn hàng."""
    order = Order.query.get_or_404(order_id)
    _restore_stock_before_delete(order)
    db.session.delete(order)
    db.session.commit()
    flash(f"Đã xóa đơn hàng #{order.order_code} thành công!", "success")
    return redirect(url_for("admin_orders"))


@admin_required
def admin_orders_bulk_action():
    """Update status or delete multiple orders in one transaction."""
    order_ids = []
    for raw_id in request.form.getlist("order_ids"):
        try:
            order_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue

    if not order_ids:
        flash("Hãy chọn ít nhất một đơn hàng.", "warning")
        return redirect(url_for("admin_orders"))

    orders = (
        Order.query.options(selectinload(Order.items).selectinload(OrderItem.product))
        .filter(Order.id.in_(set(order_ids)))
        .all()
    )
    if not orders:
        flash("Không tìm thấy đơn hàng đã chọn.", "warning")
        return redirect(url_for("admin_orders"))

    action = request.form.get("bulk_action", "")
    if action == "delete":
        for order in orders:
            _restore_stock_before_delete(order)
            db.session.delete(order)
        db.session.commit()
        flash(f"Đã xóa {len(orders)} đơn hàng.", "success")
    elif action.startswith("status:"):
        new_status = action.partition(":")[2]
        if new_status not in VALID_ORDER_STATUSES:
            flash("Trạng thái đơn hàng không hợp lệ.", "error")
            return redirect(url_for("admin_orders"))
        for order in orders:
            _set_order_status(order, new_status)
        db.session.commit()
        flash(f"Đã cập nhật trạng thái cho {len(orders)} đơn hàng.", "success")
    else:
        flash("Hãy chọn thao tác hàng loạt.", "warning")

    return redirect(url_for("admin_orders"))


def register_routes(app):
    """Register handlers, retaining the public endpoint names."""
    app.route("/admin/orders")(admin_orders)
    app.route("/admin/orders/<int:order_id>/status", methods=["POST"])(admin_order_update_status)
    app.route("/admin/orders/<int:order_id>/delete", methods=["POST"])(admin_order_delete)
    app.route("/admin/orders/bulk", methods=["POST"])(admin_orders_bulk_action)
