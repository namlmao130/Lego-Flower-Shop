"""Security."""

import urllib.parse
from functools import wraps

from flask import abort, redirect, request, url_for
from flask_login import current_user

from app.extensions import db, login_manager
from app.models import Admin, Customer


def load_user(user_id):
    try:
        account_type, raw_id = user_id.split("-", 1)
        raw_id = int(raw_id)
    except (ValueError, AttributeError):
        return None

    if account_type == "admin":
        return db.session.get(Admin, raw_id)
    elif account_type == "customer":
        return db.session.get(Customer, raw_id)
    return None


def admin_required(f):
    """Giống @login_required nhưng BẮT BUỘC phải là tài khoản Admin.
    Quan trọng: nếu không có kiểm tra này, 1 khách hàng đã đăng nhập (Customer) cũng có thể
    truy cập được các route quản trị vì current_user.is_authenticated vẫn là True."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("admin_login", next=request.path))
        if not isinstance(current_user, Admin):
            abort(403)
        return f(*args, **kwargs)

    return decorated


def customer_required(f):
    """Bắt buộc người dùng phải đăng nhập và là tài khoản Khách hàng (Customer)."""

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("login", next=request.path))
        if not isinstance(current_user, Customer):
            abort(403)
        return f(*args, **kwargs)

    return decorated


def csrf_protect_origin():
    """Bảo vệ chống tấn công CSRF (Cross-Site Request Forgery) trên các yêu cầu thay đổi trạng thái (POST, PUT, DELETE, PATCH).
    Kiểm tra Origin hoặc Referer phải xuất phát từ chính tên miền của máy chủ."""
    if request.method in ("POST", "PUT", "DELETE", "PATCH"):
        origin = request.headers.get("Origin")
        referer = request.headers.get("Referer")
        target_host = request.host.lower()

        if origin:
            parsed_origin = urllib.parse.urlparse(origin).netloc.lower()
            if parsed_origin != target_host:
                abort(403)
        elif referer:
            parsed_referer = urllib.parse.urlparse(referer).netloc.lower()
            if parsed_referer != target_host:
                abort(403)


def add_header(response):
    # Ngăn trình duyệt lưu cache trang HTML, đảm bảo xóa/sửa là trang web cập nhật ngay khi F5 hoặc quay lại
    if response.content_type and "text/html" in response.content_type:
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    elif request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
    # Ảnh/video/CSS/JS trong static/ được cache tối ưu 7 ngày (kết hợp cache-busting v=1.5 khi có thay đổi)
    elif request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=604800, immutable"

    # CÁC HEADER BẢO MẬT BẮT BUỘC (DEFENSE-IN-DEPTH)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob: https://zalo.me; "
        "media-src 'self' blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'self';"
    )

    return response


def register(app):
    """Register handlers, retaining the public endpoint names."""
    login_manager.user_loader(load_user)
    app.before_request(csrf_protect_origin)
    app.after_request(add_header)
