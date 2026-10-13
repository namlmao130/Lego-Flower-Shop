"""Routes / chat."""

from flask import abort, jsonify, make_response, request
from flask_login import current_user
from sqlalchemy import func

from app.extensions import db, limiter
from app.models import Admin, ChatMessage, Customer
from app.models.chat import ChatAttachment
from app.services.chat_image_service import prepare_chat_image
from app.services.chat_service import current_chat_session_id, merge_guest_chat_for_customer


@limiter.limit("20 per minute")
def api_chat_send():
    """Khách hàng gửi tin nhắn lên server."""
    data = request.get_json(silent=True) or request.form
    message = (data.get("message") or "").strip()
    try:
        image_data = prepare_chat_image(request.files.get("image"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if not message and image_data is None:
        return jsonify({"error": "Tin nhắn không được để trống"}), 400
    if len(message) > 2000:
        return jsonify({"error": "Tin nhắn quá dài (tối đa 2000 ký tự)"}), 400

    session_id = current_chat_session_id()
    customer_id = None
    sender_name = "Khách vãng lai"

    if current_user.is_authenticated and isinstance(current_user, Customer):
        customer_id = current_user.id
        sender_name = current_user.full_name or f"Khách hàng #{current_user.id}"
        session_id = merge_guest_chat_for_customer()

    msg = ChatMessage(
        session_id=session_id,
        customer_id=customer_id,
        sender_type="customer",
        sender_name=sender_name,
        message=message,
        is_read=False,
    )
    if image_data is not None:
        msg.attachment = ChatAttachment(image_data=image_data)
    db.session.add(msg)
    db.session.commit()

    return jsonify({"success": True, "message": msg.to_dict()})


@limiter.limit("60 per minute")
def api_chat_messages():
    """Khách hàng lấy danh sách tin nhắn của phiên chat hiện tại."""
    after_id = request.args.get("after_id", 0, type=int)
    session_id = merge_guest_chat_for_customer()

    query = ChatMessage.query.filter_by(session_id=session_id)
    if after_id > 0:
        query = query.filter(ChatMessage.id > after_id)

    msgs = query.order_by(ChatMessage.id.asc()).all()

    # Đánh dấu các tin nhắn của Admin gửi cho khách này là đã đọc (chỉ commit khi thực sự có tin mới chưa đọc)
    if any(m.sender_type == "admin" and not m.is_read for m in msgs):
        ChatMessage.query.filter_by(
            session_id=session_id, sender_type="admin", is_read=False
        ).update({"is_read": True})
        db.session.commit()

    read_through_id = (
        db.session.query(func.max(ChatMessage.id))
        .filter_by(session_id=session_id, sender_type="customer", is_read=True)
        .scalar()
        or 0
    )
    return jsonify(
        {
            "messages": [m.to_dict() for m in msgs],
            "session_id": session_id,
            "customer_read_through_id": read_through_id,
        }
    )


def api_chat_image(message_id):
    """Authorize each read; attachments never have public static URLs."""
    session_id = merge_guest_chat_for_customer()
    msg = db.session.get(ChatMessage, message_id)
    is_admin = current_user.is_authenticated and isinstance(current_user, Admin)
    if not msg or (not is_admin and msg.session_id != session_id) or not msg.attachment:
        abort(404)
    response = make_response(msg.attachment.image_data)
    response.headers["Content-Type"] = "image/webp"
    response.headers["Content-Disposition"] = f'inline; filename="chat-{message_id}.webp"'
    response.headers["Cache-Control"] = "private, no-store"
    return response


def register_routes(app):
    """Register handlers, retaining the public endpoint names."""
    app.route("/api/chat/send", methods=["POST"])(api_chat_send)
    app.route("/api/chat/messages", methods=["GET"])(api_chat_messages)
    app.route("/api/chat/images/<int:message_id>", methods=["GET"])(api_chat_image)
