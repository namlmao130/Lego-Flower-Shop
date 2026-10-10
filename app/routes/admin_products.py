"""Routes / admin products."""

import os

from flask import current_app as app
from flask import flash, redirect, render_template, request, url_for

from app.extensions import db
from app.models import Product, ProductMedia, Review
from app.security import admin_required
from app.services.catalog_service import get_cached_categories
from app.services.image_service import save_media_files


@admin_required
def admin_add_product():
    categories = get_cached_categories()

    if request.method == "POST":
        name = request.form.get("name")
        price = request.form.get("price")
        description = request.form.get("description")
        stock = request.form.get("stock", 0)
        category_id = request.form.get("category_id") or None

        new_product = Product(
            name=name,
            price=float(price),
            description=description,
            stock=int(stock),
            category_id=category_id,
        )
        db.session.add(new_product)
        db.session.flush()  # để có new_product.id trước khi lưu file

        # Lưu nhiều ảnh/video cùng lúc
        media_files = request.files.getlist("media")
        for media in save_media_files(media_files, new_product.id):
            db.session.add(media)

        db.session.commit()
        flash("Đã thêm sản phẩm thành công!", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin/add_product.html", categories=categories)


@admin_required
def admin_edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    categories = get_cached_categories()

    if request.method == "POST":
        product.name = request.form.get("name")
        product.price = float(request.form.get("price"))
        product.description = request.form.get("description")
        product.stock = int(request.form.get("stock", 0))
        product.category_id = request.form.get("category_id") or None

        # Thêm ảnh/video mới (không xóa ảnh cũ, xóa riêng qua nút Xóa ở từng ảnh)
        media_files = request.files.getlist("media")
        for media in save_media_files(media_files, product.id):
            db.session.add(media)

        db.session.commit()
        flash("Đã cập nhật sản phẩm!", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin/edit_product.html", product=product, categories=categories)


@admin_required
def admin_delete_media(media_id):
    media = ProductMedia.query.get_or_404(media_id)
    product_id = media.product_id
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], media.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(media)
    db.session.commit()
    flash("Đã xóa ảnh/video!", "success")
    return redirect(url_for("admin_edit_product", product_id=product_id))


@admin_required
def admin_delete_review(review_id):
    # Cho phép admin xóa các đánh giá spam / không phù hợp
    review = Review.query.get_or_404(review_id)
    product_id = review.product_id
    db.session.delete(review)
    db.session.commit()
    flash("Đã xóa đánh giá!", "success")
    return redirect(url_for("product_detail", product_id=product_id))


@admin_required
def admin_delete_product(product_id):
    product = Product.query.get_or_404(product_id)

    # 1. Xóa toàn bộ file ảnh / video liên quan trong thư mục static/uploads
    for m in product.media:
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], m.filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass

    if product.image:
        old_filepath = os.path.join(app.config["UPLOAD_FOLDER"], product.image)
        if os.path.exists(old_filepath):
            try:
                os.remove(old_filepath)
            except OSError:
                pass

    # 2. Xóa bản ghi trong database
    db.session.delete(product)
    db.session.commit()
    flash("Đã xóa sản phẩm thành công!", "success")
    return redirect(url_for("admin_dashboard"))


@admin_required
def admin_delete_multiple():
    product_ids = request.form.getlist("product_ids")
    if not product_ids:
        flash("Chưa chọn sản phẩm nào để xóa!", "error")
        return redirect(url_for("admin_dashboard"))

    deleted_count = 0
    for pid in product_ids:
        try:
            product = Product.query.get(int(pid))
            if product:
                # Xóa toàn bộ file ảnh / video liên quan trong thư mục static/uploads
                for m in product.media:
                    filepath = os.path.join(app.config["UPLOAD_FOLDER"], m.filename)
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except OSError:
                            pass

                if product.image:
                    old_filepath = os.path.join(app.config["UPLOAD_FOLDER"], product.image)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except OSError:
                            pass

                db.session.delete(product)
                deleted_count += 1
        except Exception as e:
            print(f"Lỗi khi xóa sản phẩm {pid}: {e}")

    db.session.commit()
    flash(f"Đã xóa thành công {deleted_count} sản phẩm!", "success")
    return redirect(url_for("admin_dashboard"))


def register_routes(app):
    """Register handlers, retaining the public endpoint names."""
    app.route("/admin/add", methods=["GET", "POST"])(admin_add_product)
    app.route("/admin/edit/<int:product_id>", methods=["GET", "POST"])(admin_edit_product)
    app.route("/admin/media/delete/<int:media_id>", methods=["POST"])(admin_delete_media)
    app.route("/admin/review/delete/<int:review_id>", methods=["POST"])(admin_delete_review)
    app.route("/admin/delete/<int:product_id>", methods=["POST"])(admin_delete_product)
    app.route("/admin/delete_multiple", methods=["POST"])(admin_delete_multiple)
