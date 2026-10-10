"""Own chat identities on the server instead of trusting browser-provided IDs."""

import secrets

from flask import session
from flask_login import current_user
from sqlalchemy import or_

from app.extensions import db
from app.models import ChatMessage, Customer

GUEST_CHAT_SESSION_KEY = "chat_guest_session_id"


def current_chat_session_id():
    if current_user.is_authenticated and isinstance(current_user, Customer):
        return f"cust_{current_user.id}"
    session_id = session.get(GUEST_CHAT_SESSION_KEY)
    if not session_id:
        session_id = "guest_" + secrets.token_urlsafe(24)
        session[GUEST_CHAT_SESSION_KEY] = session_id
    return session_id


def merge_guest_chat_for_customer():
    """Merge only the guest conversation bound to this signed browser session."""
    if not current_user.is_authenticated or not isinstance(current_user, Customer):
        return current_chat_session_id()
    canonical = f"cust_{current_user.id}"
    guest_session = session.get(GUEST_CHAT_SESSION_KEY)
    filters = [ChatMessage.customer_id == current_user.id]
    if guest_session:
        filters.append(ChatMessage.session_id == guest_session)
    changed = ChatMessage.query.filter(or_(*filters), ChatMessage.session_id != canonical).update(
        {
            "session_id": canonical,
            "customer_id": current_user.id,
            "sender_name": current_user.full_name or f"Khách hàng #{current_user.id}",
        },
        synchronize_session=False,
    )
    if changed:
        db.session.commit()
    return canonical
