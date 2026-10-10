"""Routes / admin categories."""

from flask import flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Category
from app.security import admin_required
from app.services.catalog_service import get_cached_categories, invalidate_categories_cache


@admin_required
def admin_categories():
    categories = get_cached_categories()
    return render_template("admin/categories.html", categories=categories)


@admin_required
def admin_add_category():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if name:
            db.session.add(Category(name=name))
            db.session.commit()
            invalidate_categories_cache()
            flash("Đã thêm danh mục!", "success")
        else:
            flash("Tên danh mục không được để trống!", "error")
        return redirect(url_for("admin_categories"))
    return render_template("admin/add_category.html")


@admin_required
def admin_edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    if request.method == "POST":
        category.name = request.form.get("name", "").strip()
        db.session.commit()
        invalidate_categories_cache()
        flash("Đã cập nhật danh mục!", "success")
        return redirect(url_for("admin_categories"))
    return render_template("admin/edit_category.html", category=category)


@admin_required
def admin_delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    # Sản phẩm thuộc danh mục này sẽ chuyển về "không có danh mục" thay vì bị xóa theo
    for product in category.products:
        product.category_id = None
    db.session.delete(category)
    db.session.commit()
    invalidate_categories_cache()
    flash("Đã xóa danh mục!", "success")
    return redirect(url_for("admin_categories"))


def register_routes(app):
    """Register handlers, retaining the public endpoint names."""
    app.route("/admin/categories")(admin_categories)
    app.route("/admin/categories/add", methods=["GET", "POST"])(admin_add_category)
    app.route("/admin/categories/edit/<int:category_id>", methods=["GET", "POST"])(
        admin_edit_category
    )
    app.route("/admin/categories/delete/<int:category_id>", methods=["POST"])(admin_delete_category)
