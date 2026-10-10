"""Routes / auth."""

import hmac
import secrets

from flask import current_app as app
from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from itsdangerous import BadData, SignatureExpired
from sqlalchemy import func

from app.extensions import db, limiter
from app.models import Customer
from app.services.email_service import get_reset_serializer, send_password_reset_email
from app.validators import EMAIL_REGEX, PHONE_REGEX, normalize_phone


@limiter.limit("5 per minute, 15 per hour")
def register():
    if current_user.is_authenticated and isinstance(current_user, Customer):
        return redirect(url_for("index"))

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        phone = normalize_phone(request.form.get("phone", ""))
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        errors = []
        if not full_name:
            errors.append("Vui lòng nhập họ tên.")
        if not phone or not PHONE_REGEX.match(phone):
            errors.append(
                "Số điện thoại không hợp lệ. Số di động Việt Nam gồm đúng 10 chữ số (VD: 0912345678)."
            )
        elif Customer.query.filter_by(phone=phone).first():
            errors.append("Số điện thoại này đã được đăng ký.")

        if not email:
            errors.append("Vui lòng nhập địa chỉ email.")
        elif not EMAIL_REGEX.match(email):
            errors.append("Địa chỉ email không đúng định dạng (VD: example@gmail.com).")
        elif Customer.query.filter(func.lower(Customer.email) == email).first():
            errors.append("Địa chỉ email này đã được sử dụng.")

        if len(password) < 6:
            errors.append("Mật khẩu phải có ít nhất 6 ký tự.")
        elif password != password2:
            errors.append("Mật khẩu nhập lại không khớp.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("register.html", full_name=full_name, phone=phone, email=email)

        customer = Customer(phone=phone, email=email, full_name=full_name[:100])
        customer.set_password(password)
        db.session.add(customer)
        db.session.commit()

        login_user(customer, remember=True)
        flash(f"Chào mừng {customer.full_name} đã tham gia Lego Flower!", "success")
        return redirect(url_for("index"))

    return render_template("register.html")


@limiter.limit("5 per minute, 25 per hour")
def login():
    if current_user.is_authenticated and isinstance(current_user, Customer):
        return redirect(url_for("index"))

    if request.method == "POST":
        identifier = request.form.get("login_identifier", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        customer = None
        if "@" in identifier:
            customer = Customer.query.filter(
                func.lower(Customer.email) == identifier.lower()
            ).first()
        else:
            phone = normalize_phone(identifier)
            customer = Customer.query.filter_by(phone=phone).first()

        if customer and customer.check_password(password):
            login_user(customer, remember=remember)
            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("index"))
        else:
            flash("Số điện thoại/Email hoặc mật khẩu không chính xác!", "error")
            return render_template("login.html", login_identifier=identifier)

    return render_template("login.html")


@limiter.limit("3 per minute, 10 per hour")
def forgot_password():
    if current_user.is_authenticated and isinstance(current_user, Customer):
        return redirect(url_for("index"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        if not email or not EMAIL_REGEX.match(email):
            flash("Vui lòng nhập địa chỉ email hợp lệ.", "error")
            return render_template("forgot_password.html", email=email)

        customer = Customer.query.filter(func.lower(Customer.email) == email).first()
        if customer:
            serializer = get_reset_serializer()
            verification_code = f"{secrets.randbelow(1_000_000):06d}"
            token = serializer.dumps(
                {"email": customer.email, "code": verification_code}, salt="password-reset-salt"
            )
            reset_url = url_for("reset_password", token=token, _external=True)
            sent, error = send_password_reset_email(customer.email, reset_url, verification_code)
            if not sent:
                app.logger.error(
                    "Không thể gửi email đặt lại mật khẩu cho %s: %s", customer.email, error
                )
                flash(
                    "Hệ thống chưa thể gửi mã xác thực. Vui lòng thử lại sau hoặc liên hệ cửa hàng.",
                    "error",
                )
                return render_template("forgot_password.html", email=email)

        flash(
            "Nếu email của bạn tồn tại trong hệ thống, chúng tôi đã gửi mã xác thực và liên kết đặt lại mật khẩu. Vui lòng kiểm tra hộp thư (kể cả mục Spam/Thư rác).",
            "success",
        )
        return redirect(url_for("login"))

    return render_template("forgot_password.html")


@limiter.limit("10 per minute")
def reset_password(token):
    if current_user.is_authenticated and isinstance(current_user, Customer):
        return redirect(url_for("index"))

    serializer = get_reset_serializer()
    try:
        reset_payload = serializer.loads(token, salt="password-reset-salt", max_age=1800)
        # Hỗ trợ các liên kết cũ đã phát hành trước khi bổ sung mã xác thực.
        if isinstance(reset_payload, dict):
            email = reset_payload.get("email", "")
            expected_code = str(reset_payload.get("code", ""))
        else:
            email = str(reset_payload)
            expected_code = ""
    except SignatureExpired:
        flash(
            "Liên kết đặt lại mật khẩu đã hết hạn (chỉ có hiệu lực trong 30 phút). Vui lòng yêu cầu lại.",
            "error",
        )
        return redirect(url_for("forgot_password"))
    except BadData:
        flash("Liên kết đặt lại mật khẩu không hợp lệ.", "error")
        return redirect(url_for("forgot_password"))

    customer = Customer.query.filter(func.lower(Customer.email) == email.lower()).first()
    if not customer:
        flash("Tài khoản không tồn tại.", "error")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        verification_code = request.form.get("verification_code", "").strip()
        password = request.form.get("password", "")
        password2 = request.form.get("password2", "")

        if expected_code and not hmac.compare_digest(verification_code, expected_code):
            flash("Mã xác thực không chính xác. Vui lòng kiểm tra lại email.", "error")
            return render_template("reset_password.html", token=token, requires_code=True)
        if len(password) < 6:
            flash("Mật khẩu mới phải có ít nhất 6 ký tự.", "error")
            return render_template(
                "reset_password.html", token=token, requires_code=bool(expected_code)
            )
        if password != password2:
            flash("Mật khẩu xác nhận không khớp.", "error")
            return render_template(
                "reset_password.html", token=token, requires_code=bool(expected_code)
            )

        customer.set_password(password)
        db.session.commit()
        flash(
            "Đặt lại mật khẩu thành công! Bạn có thể đăng nhập bằng mật khẩu mới ngay bây giờ.",
            "success",
        )
        return redirect(url_for("login"))

    return render_template("reset_password.html", token=token, requires_code=bool(expected_code))


@login_required
def logout():
    if isinstance(current_user, Customer):
        logout_user()
    return redirect(url_for("index"))


def register_routes(app):
    """Register handlers, retaining the public endpoint names."""
    app.route("/register", methods=["GET", "POST"])(register)
    app.route("/login", methods=["GET", "POST"])(login)
    app.route("/forgot-password", methods=["GET", "POST"])(forgot_password)
    app.route("/reset-password/<token>", methods=["GET", "POST"])(reset_password)
    app.route("/logout")(logout)
