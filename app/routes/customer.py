"""Routes / customer."""

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func

from app.extensions import db
from app.models import Customer, Order, Review
from app.security import customer_required
from app.services.image_service import process_and_save_avatar, remove_old_avatar
from app.validators import EMAIL_REGEX, PHONE_REGEX, normalize_phone


@login_required
def delete_own_review(review_id):
    """Cho phép khách hàng xóa review CỦA CHÍNH MÌNH (khác route admin xóa review bất kỳ)."""
    review = Review.query.get_or_404(review_id)
    if not isinstance(current_user, Customer) or review.customer_id != current_user.id:
        abort(403)

    product_id = review.product_id
    db.session.delete(review)
    db.session.commit()
    flash("Đã xóa đánh giá của bạn.", "success")

    next_url = request.form.get("next")
    if next_url and next_url.startswith("/"):
        return redirect(next_url)
    return redirect(url_for("product_detail", product_id=product_id) + "#reviews")


@customer_required
def user_settings():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "update_avatar":
            avatar_file = request.files.get("avatar")
            if not avatar_file or not avatar_file.filename:
                flash("Vui lòng chọn một tệp ảnh để làm ảnh đại diện.", "error")
            else:
                new_avatar, err = process_and_save_avatar(avatar_file, current_user.id)
                if err:
                    flash(err, "error")
                else:
                    remove_old_avatar(current_user.avatar)
                    current_user.avatar = new_avatar
                    db.session.commit()
                    flash("Cập nhật ảnh đại diện thành công!", "success")
            return redirect(url_for("user_settings"))

        elif action == "delete_avatar":
            if current_user.avatar:
                remove_old_avatar(current_user.avatar)
                current_user.avatar = None
                db.session.commit()
                flash("Đã gỡ ảnh đại diện, chuyển về biểu tượng mặc định.", "success")
            else:
                flash("Bạn hiện chưa cài đặt ảnh đại diện riêng.", "info")
            return redirect(url_for("user_settings"))

        elif action == "update_profile":
            full_name = request.form.get("full_name", "").strip()
            phone_raw = request.form.get("phone", "").strip()
            email = request.form.get("email", "").strip().lower()
            avatar_file = request.files.get("avatar")
            errors = []

            if not full_name:
                errors.append("Họ và tên không được để trống.")

            phone = normalize_phone(phone_raw)
            if not phone or not PHONE_REGEX.match(phone):
                errors.append(
                    "Số điện thoại không hợp lệ. Số di động Việt Nam gồm đúng 10 chữ số (VD: 0912345678)."
                )
            else:
                existing_phone = Customer.query.filter(
                    Customer.phone == phone, Customer.id != current_user.id
                ).first()
                if existing_phone:
                    errors.append("Số điện thoại này đã được sử dụng bởi tài khoản khác.")

            if email:
                if not EMAIL_REGEX.match(email):
                    errors.append("Địa chỉ email không đúng định dạng.")
                else:
                    existing = Customer.query.filter(
                        func.lower(Customer.email) == email, Customer.id != current_user.id
                    ).first()
                    if existing:
                        errors.append("Địa chỉ email này đã được sử dụng bởi tài khoản khác.")

            if errors:
                for e in errors:
                    flash(e, "error")
            else:
                if avatar_file and avatar_file.filename:
                    new_avatar, err = process_and_save_avatar(avatar_file, current_user.id)
                    if err:
                        flash(err, "error")
                    else:
                        remove_old_avatar(current_user.avatar)
                        current_user.avatar = new_avatar

                current_user.full_name = full_name[:100]
                current_user.phone = phone
                current_user.email = email or None
                db.session.commit()
                flash("Cập nhật thông tin thành công!", "success")
            return redirect(url_for("user_settings"))

        elif action == "change_password":
            current_pwd = request.form.get("current_password", "")
            new_pwd = request.form.get("new_password", "")
            confirm_pwd = request.form.get("confirm_password", "")

            if not current_user.check_password(current_pwd):
                flash("Mật khẩu hiện tại không chính xác.", "error")
            elif len(new_pwd) < 6:
                flash("Mật khẩu mới phải có ít nhất 6 ký tự.", "error")
            elif new_pwd != confirm_pwd:
                flash("Mật khẩu xác nhận không khớp.", "error")
            else:
                current_user.set_password(new_pwd)
                db.session.commit()
                flash("Đổi mật khẩu thành công!", "success")
            return redirect(url_for("user_settings") + "#password")

    my_reviews = (
        Review.query.filter_by(customer_id=current_user.id).order_by(Review.created_at.desc()).all()
    )
    my_orders = (
        Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()
    )
    return render_template("user_settings.html", my_reviews=my_reviews, my_orders=my_orders)


def register_routes(app):
    """Register handlers, retaining the public endpoint names."""
    app.route("/review/<int:review_id>/delete", methods=["POST"])(delete_own_review)
    app.route("/settings", methods=["GET", "POST"])(user_settings)
