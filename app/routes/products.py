"""Routes / products."""

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy.orm import joinedload, selectinload

from app.extensions import db, limiter
from app.models import Customer, Product, Review
from app.services.catalog_service import get_cached_categories, product_cards_query
from app.services.search_service import clean_search_query, search_products

PRODUCTS_PER_PAGE = 24


def index():
    # Trang chủ: hỗ trợ tìm kiếm sản phẩm và lọc theo danh mục
    q = clean_search_query(request.args.get("q", ""))
    category_id = request.args.get("category", type=int)
    is_partial = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.args.get("ajax") == "1"
    )

    query = product_cards_query()
    if category_id:
        query = query.filter_by(category_id=category_id)
    query = search_products(query, q)

    if not (q or category_id):
        # TỐI ƯU HÓA TRUY VẤN TRANG CHỦ: Gom 1 lần truy vấn duy nhất lấy 8 sản phẩm mới nhất.
        # 6 sản phẩm đầu tiên hiển thị trên carousel, toàn bộ 8 sản phẩm hiển thị ở danh sách bên dưới.
        # Tái sử dụng cùng danh sách để không truy vấn riêng cho carousel.
        products = query.order_by(Product.id.desc()).limit(8).all()
        carousel_products = products[:6]
    else:
        carousel_products = (
            []
            if is_partial
            else product_cards_query(with_ratings=False).order_by(Product.id.desc()).limit(6).all()
        )
        products = query.limit(60).all()

    # Nếu là yêu cầu AJAX (chỉ load lại phần sản phẩm bên dưới)
    if is_partial:
        return render_template(
            "_product_list_partial.html",
            products=products,
            search_query=q,
            selected_category=category_id,
        )

    categories = get_cached_categories()
    return render_template(
        "index.html",
        products=products,
        carousel_products=carousel_products,
        categories=categories,
        search_query=q,
        selected_category=category_id,
    )


def products():
    # Danh sách toàn bộ sản phẩm, có thể lọc theo category và từ khóa tìm kiếm
    q = clean_search_query(request.args.get("q", ""))
    category_id = request.args.get("category", type=int)
    page = request.args.get("page", 1, type=int)

    query = product_cards_query()
    if category_id:
        query = query.filter_by(category_id=category_id)
    query = search_products(query, q)

    # QUAN TRỌNG: trước đây dùng .all() tải HẾT 300+ sản phẩm (kèm reviews của từng
    # sản phẩm) trong 1 lần -> rất nặng khi nhiều khách cùng mở trang này.
    # paginate() chỉ tải đúng 1 trang (24 sản phẩm), nhẹ hơn rất nhiều và phản hồi nhanh
    # hơn hẳn dù có bao nhiêu sản phẩm trong catalog.
    pagination = query.paginate(page=page, per_page=PRODUCTS_PER_PAGE, error_out=False)
    products = pagination.items
    categories = get_cached_categories()

    # Hỗ trợ AJAX load nhanh không reload cả trang
    if (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.args.get("ajax") == "1"
    ):
        return render_template(
            "_product_list_partial.html",
            products=products,
            pagination=pagination,
            search_query=q,
            selected_category=category_id,
        )

    return render_template(
        "products.html",
        products=products,
        pagination=pagination,
        categories=categories,
        selected_category=category_id,
        search_query=q,
    )


def product_detail(product_id):
    product = Product.query.options(
        selectinload(Product.media),
        selectinload(Product.reviews).selectinload(Review.customer),
        joinedload(Product.category),
    ).get_or_404(product_id)

    # Lấy tối đa 4 sản phẩm cùng danh mục gợi ý thêm (loại trừ sản phẩm hiện tại)
    related_products = []
    if product.category_id:
        related_products = (
            product_cards_query(with_ratings=False)
            .filter(Product.category_id == product.category_id, Product.id != product.id)
            .order_by(Product.id.desc())
            .limit(4)
            .all()
        )
    if not related_products:
        # Nếu danh mục này không còn sp khác, lấy 4 sp mới nhất khác
        related_products = (
            product_cards_query(with_ratings=False)
            .filter(Product.id != product.id)
            .order_by(Product.id.desc())
            .limit(4)
            .all()
        )

    # Nếu khách hàng đã đăng nhập, kiểm tra xem họ đã đánh giá sản phẩm này chưa
    # (để ẩn form và hiện thông báo thay vì cho đánh giá trùng)
    my_review = None
    if current_user.is_authenticated and isinstance(current_user, Customer):
        my_review = Review.query.filter_by(
            customer_id=current_user.id, product_id=product.id
        ).first()

    return render_template(
        "product_detail.html",
        product=product,
        related_products=related_products,
        my_review=my_review,
    )


@limiter.limit("6 per minute")
def submit_review(product_id):
    # Đảm bảo sản phẩm tồn tại, nếu không sẽ tự trả về 404
    product = Product.query.get_or_404(product_id)

    is_logged_in_customer = current_user.is_authenticated and isinstance(current_user, Customer)

    # Nếu đã đăng nhập: lấy tên từ tài khoản, không tin vào tên tự nhập trên form
    # Nếu là khách vãng lai: vẫn cho phép nhập tên (giữ tương thích ngược)
    if is_logged_in_customer:
        customer_name = current_user.full_name
    else:
        customer_name = request.form.get("customer_name", "").strip()

    comment = request.form.get("comment", "").strip()
    rating_raw = request.form.get("rating", "")

    # Validate dữ liệu đầu vào - không tin tưởng dữ liệu người dùng gửi lên
    rating = None
    errors = []
    if not customer_name:
        errors.append("Vui lòng nhập tên của bạn.")
    try:
        rating = int(rating_raw)
        if rating < 1 or rating > 5:
            raise ValueError
    except (TypeError, ValueError):
        errors.append("Vui lòng chọn số sao từ 1 đến 5.")

    # Mỗi tài khoản khách hàng chỉ được đánh giá 1 lần / sản phẩm
    if (
        is_logged_in_customer
        and Review.query.filter_by(customer_id=current_user.id, product_id=product.id).first()
    ):
        errors.append("Bạn đã đánh giá sản phẩm này rồi.")

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("product_detail", product_id=product_id) + "#reviews")

    review = Review(
        product_id=product.id,
        customer_id=current_user.id if is_logged_in_customer else None,
        customer_name=customer_name[:100],
        rating=rating,
        comment=comment or None,
    )
    db.session.add(review)
    db.session.commit()
    flash("Cảm ơn bạn đã đánh giá sản phẩm!", "success")
    return redirect(url_for("product_detail", product_id=product_id) + "#reviews")


def register_routes(app):
    """Register handlers, retaining the public endpoint names."""
    app.route("/")(index)
    app.route("/products")(products)
    app.route("/product/<int:product_id>")(product_detail)
    app.route("/product/<int:product_id>/review", methods=["POST"])(submit_review)
