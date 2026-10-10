"""Services / catalog service."""

from sqlalchemy.orm import joinedload, selectinload

from app.extensions import cache
from app.models import Category, Product, Review


def get_cached_categories():
    """Danh mục gần như không đổi -> cache 10 phút thay vì query DB ở MỌI request.
    Giúp giảm tải DB đáng kể khi có nhiều khách truy cập cùng lúc, vì trước đây
    hàm này (qua context_processor) chạy 1 query cho MỌI trang, MỌI request."""
    categories = cache.get("all_categories")
    if categories is None:
        categories = Category.query.order_by(Category.name).all()
        cache.set("all_categories", categories, timeout=600)
    return categories


def invalidate_categories_cache():
    """Gọi hàm này mỗi khi thêm/sửa/xóa category để cache không bị cũ."""
    cache.delete("all_categories")


def get_categories_with_products():
    """Return session-bound categories with products loaded for admin screens.

    Cached category objects are intentionally not used here: a cached ORM object
    may be detached from the request's database session, so lazy-loading
    ``category.products`` would fail in production.
    """
    return (
        Category.query.options(selectinload(Category.products))
        .order_by(Category.name)
        .all()
    )


def product_cards_query(with_ratings=True):
    """Load only the relationships and rating fields used by product cards."""
    options = [selectinload(Product.media), joinedload(Product.category)]
    if with_ratings:
        options.append(selectinload(Product.reviews).load_only(Review.product_id, Review.rating))
    return Product.query.options(*options)
