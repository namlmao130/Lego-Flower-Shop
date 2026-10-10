"""Routes / admin chat."""

from flask import jsonify, render_template, request
from flask_login import current_user
from sqlalchemy import func, or_
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models import ChatMessage, Customer
from app.security import admin_required


@admin_required
def admin_chat():
    """Giao diện quản lý tin nhắn và chat trực tiếp với khách hàng của Admin."""
    return render_template("admin/chat.html")


@admin_required
def api_admin_chat_conversations():
    """Lấy danh sách các cuộc trò chuyện từ tất cả khách hàng (tối ưu hóa batch query)."""
    subquery = (
        db.session.query(ChatMessage.session_id, func.max(ChatMessage.id).label("max_id"))
        .group_by(ChatMessage.session_id)
        .subquery()
    )

    latest_messages = (
        db.session.query(ChatMessage)
        .join(subquery, ChatMessage.id == subquery.c.max_id)
        .options(selectinload(ChatMessage.customer))
        .order_by(ChatMessage.id.desc())
        .all()
    )

    # Tính toán số tin chưa đọc trong 1 câu query duy nhất (thay vì lặp N câu query)
    unread_map = dict(
        db.session.query(ChatMessage.session_id, func.count(ChatMessage.id))
        .filter(ChatMessage.sender_type == "customer", ChatMessage.is_read == False)
        .group_by(ChatMessage.session_id)
        .all()
    )

    conversations = []
    for msg in latest_messages:
        unread = unread_map.get(msg.session_id, 0)
        cust = msg.customer
        if not cust and msg.session_id.startswith("cust_"):
            try:
                cid = int(msg.session_id.replace("cust_", ""))
                cust = db.session.get(Customer, cid)
            except Exception:
                pass

        cust_info = {
            "id": cust.id if cust else None,
            "name": cust.full_name if cust else msg.sender_name,
            "phone": cust.phone if cust else "",
            "email": cust.email if cust else "",
            "avatar": cust.avatar if cust else None,
            "is_member": bool(cust),
        }

        conversations.append(
            {
                "session_id": msg.session_id,
                "customer": cust_info,
                "last_message": msg.message,
                "last_time": msg.created_at.strftime("%H:%M %d/%m"),
                "sender_type": msg.sender_type,
                "unread_count": unread,
            }
        )

    return jsonify({"conversations": conversations})


@admin_required
def api_admin_chat_messages(session_id):
    """Lấy toàn bộ tin nhắn trong một cuộc trò chuyện và đánh dấu đã đọc."""
    cust_id = None
    if session_id.startswith("cust_"):
        try:
            cust_id = int(session_id.replace("cust_", ""))
        except Exception:
            pass

    if cust_id:
        msgs = (
            ChatMessage.query.filter(
                or_(ChatMessage.session_id == session_id, ChatMessage.customer_id == cust_id)
            )
            .order_by(ChatMessage.id.asc())
            .all()
        )
        ChatMessage.query.filter(
            ChatMessage.customer_id == cust_id, ChatMessage.session_id != session_id
        ).update({"session_id": session_id}, synchronize_session=False)
        ChatMessage.query.filter(
            or_(ChatMessage.session_id == session_id, ChatMessage.customer_id == cust_id),
            ChatMessage.sender_type == "customer",
            ChatMessage.is_read == False,
        ).update({"is_read": True}, synchronize_session=False)
    else:
        msgs = (
            ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.id.asc()).all()
        )
        ChatMessage.query.filter_by(
            session_id=session_id, sender_type="customer", is_read=False
        ).update({"is_read": True})
    db.session.commit()

    cust = None
    if cust_id:
        cust = db.session.get(Customer, cust_id)
    if not cust:
        first_cust_msg = next((m for m in msgs if m.customer_id), None)
        cust = first_cust_msg.customer if first_cust_msg else None

    cust_info = {
        "id": cust.id if cust else None,
        "name": cust.full_name if cust else (msgs[0].sender_name if msgs else "Khách vãng lai"),
        "phone": cust.phone if cust else "",
        "email": cust.email if cust else "",
        "avatar": cust.avatar if cust else None,
        "is_member": bool(cust),
        "created_at": cust.created_at.strftime("%d/%m/%Y") if cust else "",
    }

    return jsonify({"messages": [m.to_dict() for m in msgs], "customer": cust_info})


@admin_required
def api_admin_chat_reply():
    """Admin trả lời tin nhắn của một khách hàng."""
    data = request.get_json(silent=True) or request.form
    session_id = (data.get("session_id") or "").strip()
    message = (data.get("message") or "").strip()

    if not session_id or not message:
        return jsonify({"error": "Thiếu session_id hoặc nội dung tin nhắn"}), 400

    cust_id = None
    if session_id.startswith("cust_"):
        try:
            cust_id = int(session_id.replace("cust_", ""))
        except Exception:
            pass

    if not cust_id:
        last_msg = ChatMessage.query.filter_by(session_id=session_id).first()
        cust_id = last_msg.customer_id if last_msg else None

    reply_msg = ChatMessage(
        session_id=session_id,
        customer_id=cust_id,
        sender_type="admin",
        sender_name=getattr(current_user, "username", "Quản trị viên"),
        message=message,
        is_read=False,
    )
    db.session.add(reply_msg)
    db.session.commit()

    return jsonify({"success": True, "message": reply_msg.to_dict()})


@admin_required
def api_admin_chat_unread_count():
    """Lấy tổng số tin nhắn chưa đọc từ khách hàng cho huy hiệu Admin."""
    unread_count = ChatMessage.query.filter_by(sender_type="customer", is_read=False).count()
    return jsonify({"unread_count": unread_count})


def register_routes(app):
    """Register handlers, retaining the public endpoint names."""
    app.route("/admin/chat")(admin_chat)
    app.route("/api/admin/chat/conversations")(api_admin_chat_conversations)
    app.route("/api/admin/chat/messages/<session_id>")(api_admin_chat_messages)
    app.route("/api/admin/chat/reply", methods=["POST"])(api_admin_chat_reply)
    app.route("/api/admin/chat/unread_count")(api_admin_chat_unread_count)
