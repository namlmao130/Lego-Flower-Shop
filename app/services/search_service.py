"""Portable Vietnamese catalog search without schema changes or DB extensions."""

import unicodedata

from sqlalchemy import and_, case, func, literal_column, or_

from app.extensions import db
from app.models import Category, Product


def normalize_search(value):
    value = unicodedata.normalize("NFD", value or "").lower().replace("đ", "d")
    return "".join(char for char in value if not unicodedata.combining(char))


def clean_search_query(value):
    return " ".join((value or "").split())[:200]


def _normalized(column):
    column = func.coalesce(column, "")
    if db.engine.dialect.name == "postgresql":
        # NFD separates Vietnamese accents. translate removes combining marks.
        accents = "\u0300\u0301\u0303\u0309\u0323\u0306\u0302\u031b"
        return func.lower(
            func.translate(func.normalize(column, literal_column("NFD")), "đĐ" + accents, "dD")
        )
    return func.shop_search_normalize(column)


def search_products(query, text):
    """Every word must match; rank exact name, name phrase, name words, other fields."""
    phrase = normalize_search(clean_search_query(text))
    if not phrase:
        return query.order_by(Product.id.desc())
    tokens = list(dict.fromkeys(phrase.split()))
    if not tokens:
        return query.filter(False)
    query = query.outerjoin(Category, Product.category_id == Category.id)
    name = _normalized(Product.name)
    description = _normalized(Product.description)
    category = _normalized(Category.name)
    name_words = and_(*(name.contains(word, autoescape=True) for word in tokens))
    for word in tokens:
        query = query.filter(
            or_(*(field.contains(word, autoescape=True) for field in (name, description, category)))
        )
    relevance = case(
        (name == phrase, 0),
        (name.contains(phrase, autoescape=True), 1),
        (name_words, 2),
        else_=3,
    )
    return query.order_by(relevance, Product.id.desc())
