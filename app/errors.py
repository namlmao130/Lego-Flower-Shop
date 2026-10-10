"""Errors."""

from flask import jsonify, render_template, request


def handle_error_400(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Yêu cầu không hợp lệ"}), 400
    return render_template(
        "error.html",
        code=400,
        title="Yêu cầu không hợp lệ",
        message="Yêu cầu gửi lên máy chủ không đúng định dạng hoặc thiếu tham số bắt buộc.",
    ), 400


def handle_error_403(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Từ chối truy cập (Forbidden)"}), 403
    return render_template(
        "error.html",
        code=403,
        title="Từ chối truy cập",
        message="Bạn không có quyền truy cập vào khu vực này hoặc yêu cầu bị chặn bởi cơ chế bảo vệ CSRF.",
    ), 403


def handle_error_404(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Tài nguyên không tồn tại"}), 404
    return render_template(
        "error.html",
        code=404,
        title="Không tìm thấy trang",
        message="Trang hoặc sản phẩm bạn đang tìm kiếm không tồn tại hoặc đã được gỡ bỏ.",
    ), 404


def handle_error_413(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Dữ liệu tải lên vượt quá giới hạn cho phép (tối đa 16MB)"}), 413
    return render_template(
        "error.html",
        code=413,
        title="Tệp quá lớn",
        message="Dung lượng tệp tải lên vượt quá giới hạn an toàn tối đa cho phép của máy chủ (tối đa 16MB).",
    ), 413


def handle_error_429(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Quá nhiều yêu cầu. Vui lòng thử lại sau."}), 429
    return render_template(
        "error.html",
        code=429,
        title="Quá nhiều yêu cầu",
        message="Hệ thống phát hiện tần suất gửi yêu cầu quá nhanh. Vui lòng chờ giây lát rồi thao tác tiếp.",
    ), 429


def handle_error_500(e):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Lỗi máy chủ nội bộ"}), 500
    return render_template(
        "error.html",
        code=500,
        title="Sự cố hệ thống",
        message="Đã xảy ra sự cố nội bộ. Đội ngũ kỹ thuật đã được thông báo để khắc phục sớm nhất.",
    ), 500


def register(app):
    """Register handlers, retaining the public endpoint names."""
    app.errorhandler(400)(handle_error_400)
    app.errorhandler(403)(handle_error_403)
    app.errorhandler(404)(handle_error_404)
    app.errorhandler(413)(handle_error_413)
    app.errorhandler(429)(handle_error_429)
    app.errorhandler(500)(handle_error_500)
