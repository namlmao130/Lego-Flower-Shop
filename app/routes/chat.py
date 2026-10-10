"""Routes / chat."""

from flask import jsonify, request
from flask_login import current_user
from sqlalchemy import func

from app.extensions import db, limiter
from app.models import ChatMessage, Customer
from app.services.chat_service import current_chat_session_id, merge_guest_chat_for_customer


@limiter.limit("20 per minute")
def api_chat_send():
    """Khách hàng gửi tin nhắn lên server."""
    data = request.get_json(silent=True) or request.form
    message = (data.get("message") or "").strip()
    if not message:
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


def register_routes(app):
    """Register handlers, retaining the public endpoint names."""
    app.route("/api/chat/send", methods=["POST"])(api_chat_send)
    app.route("/api/chat/messages", methods=["GET"])(api_chat_messages)
