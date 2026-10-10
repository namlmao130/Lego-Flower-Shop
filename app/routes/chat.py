"""Routes / chat."""

from flask import jsonify, request
from flask_login import current_user

from app.extensions import db, limiter
from app.models import ChatMessage, Customer


@limiter.limit("20 per minute")
def api_chat_send():
    """Khách hàng gửi tin nhắn lên server."""
    data = request.get_json(silent=True) or request.form
    session_id = (data.get("session_id") or "").strip()
    message = (data.get("message") or "").strip()
    prev_guest_session = (data.get("prev_guest_session") or "").strip()

    if not session_id:
        return jsonify({"error": "Thiếu session_id"}), 400
    if not message:
        return jsonify({"error": "Tin nhắn không được để trống"}), 400
    if len(message) > 2000:
        return jsonify({"error": "Tin nhắn quá dài (tối đa 2000 ký tự)"}), 400

    customer_id = None
    sender_name = "Khách vãng lai"

    if current_user.is_authenticated and isinstance(current_user, Customer):
        customer_id = current_user.id
        sender_name = current_user.full_name or f"Khách hàng #{current_user.id}"
        canonical_session = f"cust_{customer_id}"

        # Gộp tất cả tin nhắn từ phiên cũ (nếu có) sang canonical session để không bị tách đoạn chat
        sessions_to_merge = [
            s for s in [session_id, prev_guest_session] if s and s != canonical_session
        ]
        if sessions_to_merge:
            ChatMessage.query.filter(ChatMessage.session_id.in_(sessions_to_merge)).update(
                {
                    "session_id": canonical_session,
                    "customer_id": customer_id,
                    "sender_name": sender_name,
                },
                synchronize_session=False,
            )

        # Đảm bảo toàn bộ tin nhắn trước đây của khách này đều thuộc canonical session
        ChatMessage.query.filter(
            ChatMessage.customer_id == customer_id, ChatMessage.session_id != canonical_session
        ).update({"session_id": canonical_session}, synchronize_session=False)

        session_id = canonical_session

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
    session_id = (request.args.get("session_id") or "").strip()
    after_id = request.args.get("after_id", 0, type=int)

    if not session_id:
        return jsonify({"error": "Thiếu session_id"}), 400

    if current_user.is_authenticated and isinstance(current_user, Customer):
        canonical_session = f"cust_{current_user.id}"
        if session_id != canonical_session:
            ChatMessage.query.filter_by(session_id=session_id).update(
                {
                    "session_id": canonical_session,
                    "customer_id": current_user.id,
                    "sender_name": current_user.full_name or f"Khách hàng #{current_user.id}",
                },
                synchronize_session=False,
            )
            db.session.commit()
        session_id = canonical_session

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

    return jsonify({"messages": [m.to_dict() for m in msgs]})


def register_routes(app):
    """Register handlers, retaining the public endpoint names."""
    app.route("/api/chat/send", methods=["POST"])(api_chat_send)
    app.route("/api/chat/messages", methods=["GET"])(api_chat_messages)
