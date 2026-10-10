"""Compatibility imports for existing migration and maintenance scripts."""

from app.models import (
    Admin,
    Category,
    ChatMessage,
    Customer,
    Order,
    OrderItem,
    Product,
    ProductMedia,
    Review,
    db,
)
from app.validators import EMAIL_REGEX, PHONE_REGEX, normalize_phone

__all__ = [
    "db",
    "Category",
    "Product",
    "ProductMedia",
    "Review",
    "Customer",
    "Admin",
    "ChatMessage",
    "Order",
    "OrderItem",
    "EMAIL_REGEX",
    "PHONE_REGEX",
    "normalize_phone",
]
