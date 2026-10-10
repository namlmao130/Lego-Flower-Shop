# Cấu trúc source code

`web.py` là entry point tương thích với `gunicorn web:app`, `python web.py`
và `run_production.py`. `app.create_app()` lắp ghép các module, nhận cấu hình
override để test mà không kết nối database thật.

```text
app/
  __init__.py           # application factory
  extensions.py         # SQLAlchemy, cache, limiter, login, compression
  database.py           # schema bootstrap, indexes, SQLite/PostgreSQL setup
  security.py           # phân quyền, CSRF origin, response headers
  context.py            # dữ liệu chung của template
  errors.py             # trang lỗi HTML và JSON
  validators.py         # chuẩn hóa điện thoại, kiểm tra email
  models/
    customer.py         # Customer
    product.py          # Category, Product, ProductMedia
    order.py            # Order, OrderItem
    review.py           # Review
    admin.py            # Admin
    chat.py             # ChatMessage
  routes/
    auth.py             # đăng ký, đăng nhập, quên/đặt lại mật khẩu
    products.py         # danh sách, chi tiết, đánh giá sản phẩm
    customer.py         # hồ sơ, avatar, đánh giá của khách
    cart.py             # giỏ hàng
    checkout.py         # đọc/kiểm tra form và điều hướng thanh toán
    orders.py           # tra cứu, hủy, đặt lại đơn
    admin.py            # đăng nhập và dashboard admin
    admin_products.py   # quản lý sản phẩm và media
    admin_categories.py # quản lý danh mục
    admin_orders.py     # quản lý đơn hàng
    chat.py             # API chat khách hàng
    admin_chat.py       # API chat quản trị
    health.py           # GET /health: kết nối database + revision deploy
  services/
    email_service.py    # token, nội dung email và SMTP
    image_service.py    # xác thực, resize, lưu ảnh/video và avatar
    order_service.py    # tạo đơn + trừ kho trong một transaction
    cart_service.py     # lấy sản phẩm và tính tổng giỏ hàng
    catalog_service.py  # truy vấn product card và cache danh mục
templates/              # giữ đường dẫn hiện tại để tránh thay đổi giao diện
static/                 # giữ đường dẫn upload và mount /app/static/uploads
tests/test_app.py       # regression tests bằng database riêng, SMTP mock
```

## Quy tắc sửa code

- Route xử lý HTTP/form/session; service xử lý công việc dùng chung.
- Import `db`, `limiter`, `cache` từ `app.extensions`, model từ `app.models`.
  Không import `web` từ bên trong `app/` (tránh vòng lặp và tạo app ngoài ý muốn).
- Dùng `flask.current_app` khi đọc config trong một request/app context.
- Các module route đăng ký bằng hàm `register_routes(app)`. Không thêm
  prefix Blueprint: tên endpoint cũ được giữ cho `url_for` và navbar.
- `models.py` ở gốc chỉ re-export để các script cũ tiếp tục chạy.
- Refactor không đổi tên bảng/cột/index; không cần migrate dữ liệu lại.
- `place_order` sở hữu commit/rollback. Nếu một mặt hàng hết kho, toàn bộ đơn
  và các lần trừ kho trước đó được rollback.

## Chạy, format và kiểm tra

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe -m ruff format app tests web.py models.py config.py migrate_db.py transfer_to_postgres.py run_production.py
.\venv\Scripts\python.exe -m ruff check app tests web.py models.py config.py migrate_db.py transfer_to_postgres.py run_production.py
.\venv\Scripts\python.exe -m unittest discover -s tests -v
.\venv\Scripts\python.exe test_checkout_race.py
.\venv\Scripts\python.exe web.py
```

Test tự tạo database riêng. Email test được mock, không gửi tới người thật.
Đặt breakpoint tại route tương ứng, rồi vào service nếu lỗi thuộc gửi mail,
lưu ảnh hoặc giao dịch đơn hàng. Xem `app/database.py` nếu lỗi lúc khởi động.

## Deploy

Docker vẫn chạy `web:app`, dùng PostgreSQL qua `DATABASE_URL`.
Sau auto-deploy, kiểm tra `/health`: `status=ok` và `revision` trùng commit.
Nếu database không truy cập được, endpoint trả HTTP 503, không lộ chuỗi kết nối.

Render Free không có persistent disk: ảnh upload mới có thể mất khi redeploy.
Ảnh đã nằm trong repository được đóng gói lại trong image. Database Free đã tạo
có hạn dùng tới 08/11/2026; cần nâng cấp hoặc chuyển nhà cung cấp trước ngày đó
nếu sử dụng lâu dài. PostgreSQL không lưu nội dung file ảnh/video.
