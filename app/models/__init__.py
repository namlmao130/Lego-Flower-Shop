"""Import all models so SQLAlchemy registers every relationship."""

from app.extensions import db

from .admin import Admin
from .chat import ChatMessage
from .customer import Customer
from .order import Order, OrderItem
from .product import Category, Product, ProductMedia
from .review import Review

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
]
