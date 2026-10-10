"""Routes / admin."""

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_user, logout_user
from sqlalchemy.orm import selectinload

from app.extensions import limiter
from app.models import Admin, Product
from app.security import admin_required
from app.services.catalog_service import get_cached_categories


def admin_root():
    """Tự động chuyển hướng /admin sang dashboard hoặc trang đăng nhập."""
    if current_user.is_authenticated and isinstance(current_user, Admin):
        return redirect(url_for("admin_dashboard"))
    return redirect(url_for("admin_login"))


@limiter.limit("5 per minute, 20 per hour")
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        admin = Admin.query.filter_by(username=username).first()

        if admin and admin.check_password(password):
            login_user(admin)
            return redirect(url_for("admin_dashboard"))
        else:
            flash("Sai tên đăng nhập hoặc mật khẩu!", "error")

    return render_template("admin/login.html")


@admin_required
def admin_logout():
    logout_user()
    return redirect(url_for("admin_login"))


@admin_required
def admin_dashboard():
    q = request.args.get("q", "").strip()
    category_id = request.args.get("category", type=int)

    query = Product.query.options(selectinload(Product.media), selectinload(Product.category))
    if category_id:
        query = query.filter_by(category_id=category_id)
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%"))

    products = query.order_by(Product.id.desc()).all()
    categories = get_cached_categories()
    return render_template(
        "admin/dashboard.html",
        products=products,
        categories=categories,
        search_query=q,
        selected_category=category_id,
    )


def register_routes(app):
    """Register handlers, retaining the public endpoint names."""
    app.route("/admin/")(admin_root)
    app.route("/admin")(admin_root)
    app.route("/admin/login", methods=["GET", "POST"])(admin_login)
    app.route("/admin/logout")(admin_logout)
    app.route("/admin/dashboard")(admin_dashboard)
