"""Context."""

from flask import session

from app.services.catalog_service import get_cached_categories
from app.services.chat_service import current_chat_session_id


def inject_nav_categories():
    # Giúp mọi trang (kể cả sidebar trong base.html) đều lấy được danh sách danh mục
    return dict(nav_categories=get_cached_categories())


def inject_cart_count():
    cart = session.get("cart", {})
    total_qty = (
        sum(int(v) for v in cart.values() if isinstance(v, (int, str)) and str(v).isdigit())
        if isinstance(cart, dict)
        else 0
    )
    return dict(cart_count=total_qty)


def inject_chat_session():
    return dict(chat_session_id=current_chat_session_id())


def register(app):
    """Register handlers, retaining the public endpoint names."""
    app.context_processor(inject_nav_categories)
    app.context_processor(inject_cart_count)
    app.context_processor(inject_chat_session)
