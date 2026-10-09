import os
import time
import uuid
import hmac
import secrets
import smtplib
import urllib.parse
from datetime import datetime
from functools import wraps
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import parseaddr
from flask import Flask, render_template, request, redirect, url_for, flash, abort, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from sqlalchemy import func, event, or_
from sqlalchemy.orm import selectinload
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
try:
    from flask_compress import Compress
except ImportError:
    Compress = None
from flask_caching import Cache
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
import gzip
from PIL import Image, ImageOps

COMPRESSIBLE_MIMETYPES = (
    'text/html', 'text/css', 'text/xml', 'text/javascript',
    'application/javascript', 'application/json', 'application/xml',
    'image/svg+xml'
)

from config import Config
from models import db, Product, Category, Admin, ProductMedia, Review, Customer, ChatMessage, Order, OrderItem, PHONE_REGEX, EMAIL_REGEX, normalize_phone

app = Flask(__name__)
app.config.from_object(Config)

# QUAN TRỌNG khi chạy sau Nginx (hoặc reverse proxy trên Render/Railway):
if os.environ.get('TRUST_PROXY', 'false').lower() == 'true':
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Nén response (HTML/CSS/JS/JSON) nếu môi trường có sẵn thư viện
if Compress:
    try:
        Compress(app)
    except Exception:
        pass

# Cache RAM / Redis cho dữ liệu ít thay đổi
cache = Cache(app)

# Rate limiting chống spam, brute-force (mức mặc định cao để không cản trở duyệt web / stress test)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[app.config.get('RATELIMIT_DEFAULT', "1200 per minute, 20000 per hour")],
    storage_uri=app.config.get('RATELIMIT_STORAGE_URI', 'memory://'),
)

# Tự động tạo thư mục uploads nếu chưa tồn tại (tránh lỗi FileNotFoundError khi upload ảnh)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config.get('AVATAR_UPLOAD_FOLDER', os.path.join(app.config['UPLOAD_FOLDER'], 'avatars')), exist_ok=True)

# Khởi tạo database
db.init_app(app)

# Tối ưu hóa hiệu năng cực đại cho SQLite:
# - WAL mode: đọc và ghi đồng thời không khóa file
# - synchronous=NORMAL: giảm bớt I/O disk flush không cần thiết trong WAL mode
# - cache_size=-64000: mở rộng 64MB bộ nhớ cache RAM cho SQLite (mặc định chỉ 2MB)
# - mmap_size=268435456: Memory-mapped I/O (256MB), đọc dữ liệu trực tiếp từ RAM không tốn syscall
# - temp_store=MEMORY: bảng tạm và sắp xếp chạy trong RAM
# - busy_timeout=15000: tự động chờ tới 15s nếu có giao dịch ghi khác đang chạy
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
    with app.app_context():
        @event.listens_for(db.engine, 'connect')
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute('PRAGMA journal_mode=WAL')
            cursor.execute('PRAGMA synchronous=NORMAL')
            cursor.execute('PRAGMA cache_size=-64000')
            cursor.execute('PRAGMA mmap_size=268435456')
            cursor.execute('PRAGMA temp_store=MEMORY')
            cursor.execute('PRAGMA busy_timeout=15000')
            cursor.close()

def ensure_database_indexes():
    """Tự động đảm bảo tất cả chỉ mục (indexes) tối ưu hiệu năng tồn tại mà không làm thay đổi hay mất dữ liệu."""
    try:
        with db.engine.connect() as conn:
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_products_category_id_desc ON products(category_id, id DESC)",
                "CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id_id ON chat_messages(session_id, id ASC)",
                "CREATE INDEX IF NOT EXISTS idx_chat_messages_unread_badge ON chat_messages(sender_type, is_read)",
                "CREATE INDEX IF NOT EXISTS idx_orders_customer_created ON orders(customer_id, created_at DESC)",
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_customers_email ON customers(email) WHERE email IS NOT NULL",
            ]
            for idx_sql in indexes:
                conn.execute(db.text(idx_sql))
            if app.config['SQLALCHEMY_DATABASE_URI'].startswith('sqlite'):
                conn.execute(db.text("PRAGMA optimize"))
            conn.commit()
    except Exception:
        pass

with app.app_context():
    ensure_database_indexes()

# Khởi tạo Flask-Login — dùng chung cho cả Admin (quản trị) và Customer (khách hàng).
# Hai loại tài khoản được phân biệt bằng tiền tố trong get_id(): "admin-<id>" / "customer-<id>"
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'  # nếu chưa login mà vào trang admin -> đá về đây


@login_manager.user_loader
def load_user(user_id):
    try:
        account_type, raw_id = user_id.split('-', 1)
        raw_id = int(raw_id)
    except (ValueError, AttributeError):
        return None

    if account_type == 'admin':
        return db.session.get(Admin, raw_id)
    elif account_type == 'customer':
        return db.session.get(Customer, raw_id)
    return None


def admin_required(f):
    """Giống @login_required nhưng BẮT BUỘC phải là tài khoản Admin.
    Quan trọng: nếu không có kiểm tra này, 1 khách hàng đã đăng nhập (Customer) cũng có thể
    truy cập được các route quản trị vì current_user.is_authenticated vẫn là True."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('admin_login', next=request.path))
        if not isinstance(current_user, Admin):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def customer_required(f):
    """Bắt buộc người dùng phải đăng nhập và là tài khoản Khách hàng (Customer)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.path))
        if not isinstance(current_user, Customer):
            abort(403)
        return f(*args, **kwargs)
    return decorated


def get_cached_categories():
    """Danh mục gần như không đổi -> cache 10 phút thay vì query DB ở MỌI request.
    Giúp giảm tải DB đáng kể khi có nhiều khách truy cập cùng lúc, vì trước đây
    hàm này (qua context_processor) chạy 1 query cho MỌI trang, MỌI request."""
    categories = cache.get('all_categories')
    if categories is None:
        categories = Category.query.order_by(Category.name).all()
        cache.set('all_categories', categories, timeout=600)
    return categories


def invalidate_categories_cache():
    """Gọi hàm này mỗi khi thêm/sửa/xóa category để cache không bị cũ."""
    cache.delete('all_categories')


@app.context_processor
def inject_nav_categories():
    # Giúp mọi trang (kể cả sidebar trong base.html) đều lấy được danh sách danh mục
    return dict(nav_categories=get_cached_categories())


@app.context_processor
def inject_cart_count():
    cart = session.get('cart', {})
    total_qty = sum(int(v) for v in cart.values() if isinstance(v, (int, str)) and str(v).isdigit()) if isinstance(cart, dict) else 0
    return dict(cart_count=total_qty)


def generate_order_code():
    """Tạo mã đơn hàng dạng LF + NămThángNgày + 4 ký tự ngẫu nhiên (VD: LF261002A1B2)"""
    now_str = datetime.now().strftime('%y%m%d')
    rand_str = uuid.uuid4().hex[:4].upper()
    return f"LF{now_str}{rand_str}"


def get_cart_details():
    """Lấy danh sách sản phẩm, tổng tiền và tổng số lượng từ session cart (truy vấn 1 lần duy nhất)."""
    cart = session.get('cart', {})
    items = []
    total_price = 0
    total_quantity = 0

    if not isinstance(cart, dict):
        cart = {}

    to_remove = []
    pids = []
    valid_entries = []
    for pid_str, qty in list(cart.items()):
        try:
            pid = int(pid_str)
            qty = int(qty)
            if qty > 0:
                pids.append(pid)
                valid_entries.append((pid_str, pid, qty))
            else:
                to_remove.append(pid_str)
        except (ValueError, TypeError):
            to_remove.append(pid_str)

    products_by_id = {}
    if pids:
        prods = Product.query.options(selectinload(Product.media)).filter(Product.id.in_(pids)).all()
        products_by_id = {p.id: p for p in prods}

    for pid_str, pid, qty in valid_entries:
        product = products_by_id.get(pid)
        if not product:
            to_remove.append(pid_str)
            continue
        subtotal = product.price * qty
        total_price += subtotal
        total_quantity += qty
        items.append({
            'product': product,
            'quantity': qty,
            'subtotal': subtotal,
            'in_stock': product.stock >= qty,
            'available_stock': product.stock
        })

    if to_remove:
        for r in to_remove:
            cart.pop(r, None)
        session['cart'] = cart
        session.modified = True

    return items, total_price, total_quantity


@app.before_request
def csrf_protect_origin():
    """Bảo vệ chống tấn công CSRF (Cross-Site Request Forgery) trên các yêu cầu thay đổi trạng thái (POST, PUT, DELETE, PATCH).
    Kiểm tra Origin hoặc Referer phải xuất phát từ chính tên miền của máy chủ."""
    if request.method in ('POST', 'PUT', 'DELETE', 'PATCH'):
        origin = request.headers.get('Origin')
        referer = request.headers.get('Referer')
        target_host = request.host.lower()

        if origin:
            parsed_origin = urllib.parse.urlparse(origin).netloc.lower()
            if parsed_origin != target_host:
                abort(403)
        elif referer:
            parsed_referer = urllib.parse.urlparse(referer).netloc.lower()
            if parsed_referer != target_host:
                abort(403)


@app.after_request
def add_header(response):
    # Ngăn trình duyệt lưu cache trang HTML, đảm bảo xóa/sửa là trang web cập nhật ngay khi F5 hoặc quay lại
    if response.content_type and 'text/html' in response.content_type:
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    elif request.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
    # Ảnh/video/CSS/JS trong static/ được cache tối ưu 7 ngày (kết hợp cache-busting v=1.5 khi có thay đổi)
    elif request.path.startswith('/static/'):
        response.headers['Cache-Control'] = 'public, max-age=604800, immutable'

    # CÁC HEADER BẢO MẬT BẮT BUỘC (DEFENSE-IN-DEPTH)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), camera=(), microphone=(), payment=()'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob: https://zalo.me; "
        "media-src 'self' blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'self';"
    )

    # TỰ ĐỘNG NÉN GZIP HIỆU NĂNG CAO: Giảm 75-85% dung lượng HTML, CSS, JS, JSON gửi qua mạng
    accept_encoding = request.headers.get('Accept-Encoding', '')
    if 'gzip' in accept_encoding.lower() and 200 <= response.status_code < 300:
        if 'Content-Encoding' not in response.headers and not response.direct_passthrough:
            c_type = (response.content_type or '').split(';')[0].strip().lower()
            if any(c_type.startswith(m) for m in COMPRESSIBLE_MIMETYPES):
                body = response.get_data()
                if len(body) >= 500:
                    compressed = gzip.compress(body, compresslevel=6)
                    if len(compressed) < len(body):
                        response.set_data(compressed)
                        response.headers['Content-Encoding'] = 'gzip'
                        response.headers['Content-Length'] = len(compressed)
                        response.headers['Vary'] = 'Accept-Encoding'

    return response


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def get_media_type(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    return 'video' if ext in app.config['ALLOWED_VIDEO_EXTENSIONS'] else 'image'


def is_valid_image_content(file_stream):
    """Xác thực nội dung file thực sự là ảnh hợp lệ, ngăn chặn tải file thực thi/script trá hình."""
    try:
        file_stream.seek(0)
        with Image.open(file_stream) as img:
            img.verify()
        file_stream.seek(0)
        return True
    except Exception:
        file_stream.seek(0)
        return False


def save_media_files(files, product_id):
    """Lưu nhiều file ảnh/video, trả về danh sách ProductMedia đã tạo (chưa commit).
    Tự động chuẩn hóa và nén tối ưu dung lượng ảnh sản phẩm nếu kích thước quá lớn."""
    saved = []
    for file in files:
        if file and file.filename and allowed_file(file.filename):
            media_type = get_media_type(file.filename)
            if media_type == 'image' and not is_valid_image_content(file.stream):
                continue
            filename = secure_filename(f"{product_id}_{file.filename}")
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)

            if media_type == 'image':
                try:
                    file.stream.seek(0)
                    with Image.open(file.stream) as img:
                        img = ImageOps.exif_transpose(img)
                        max_dim = 1400
                        if max(img.size) > max_dim:
                            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

                        fmt = img.format or ('PNG' if filename.lower().endswith('.png') else 'JPEG')
                        if fmt.upper() in ('JPEG', 'JPG'):
                            img = img.convert('RGB')
                            img.save(save_path, format='JPEG', quality=86, optimize=True)
                        elif fmt.upper() == 'PNG':
                            img.save(save_path, format='PNG', optimize=True)
                        elif fmt.upper() == 'WEBP':
                            img.save(save_path, format='WEBP', quality=86, method=6)
                        else:
                            file.stream.seek(0)
                            file.save(save_path)
                except Exception:
                    file.stream.seek(0)
                    file.save(save_path)
            else:
                file.save(save_path)

            saved.append(ProductMedia(
                product_id=product_id,
                filename=filename,
                media_type=media_type
            ))
    return saved


# ============================================
#   TRANG PUBLIC (không cần login)
# ============================================

@app.route('/')
def index():
    # Trang chủ: hỗ trợ tìm kiếm sản phẩm và lọc theo danh mục
    q = request.args.get('q', '').strip()
    category_id = request.args.get('category', type=int)

    query = Product.query.options(
        selectinload(Product.reviews),
        selectinload(Product.media),
        selectinload(Product.category)
    )
    if category_id:
        query = query.filter_by(category_id=category_id)
    if q:
        query = query.filter(Product.name.ilike(f'%{q}%'))

    if not (q or category_id):
        # TỐI ƯU HÓA TRUY VẤN TRANG CHỦ: Gom 1 lần truy vấn duy nhất lấy 8 sản phẩm mới nhất.
        # 6 sản phẩm đầu tiên hiển thị trên carousel, toàn bộ 8 sản phẩm hiển thị ở danh sách bên dưới.
        # Giảm hơn 60% số câu truy vấn SQL trên trang chủ (từ 8 câu xuống còn 3 câu)!
        products = query.order_by(Product.id.desc()).limit(8).all()
        carousel_products = products[:6]
    else:
        carousel_products = Product.query.options(
            selectinload(Product.reviews),
            selectinload(Product.media),
            selectinload(Product.category)
        ).order_by(Product.id.desc()).limit(6).all()
        products = query.order_by(Product.id.desc()).limit(60).all()

    # Nếu là yêu cầu AJAX (chỉ load lại phần sản phẩm bên dưới)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('ajax') == '1':
        return render_template(
            '_product_list_partial.html',
            products=products,
            search_query=q,
            selected_category=category_id
        )

    categories = get_cached_categories()
    return render_template(
        'index.html',
        products=products,
        carousel_products=carousel_products,
        categories=categories,
        search_query=q,
        selected_category=category_id
    )


PRODUCTS_PER_PAGE = 24


@app.route('/products')
def products():
    # Danh sách toàn bộ sản phẩm, có thể lọc theo category và từ khóa tìm kiếm
    q = request.args.get('q', '').strip()
    category_id = request.args.get('category', type=int)
    page = request.args.get('page', 1, type=int)

    query = Product.query.options(
        selectinload(Product.reviews),
        selectinload(Product.media),
        selectinload(Product.category)
    )
    if category_id:
        query = query.filter_by(category_id=category_id)
    if q:
        query = query.filter(Product.name.ilike(f'%{q}%'))
    query = query.order_by(Product.id.desc())

    # QUAN TRỌNG: trước đây dùng .all() tải HẾT 300+ sản phẩm (kèm reviews của từng
    # sản phẩm) trong 1 lần -> rất nặng khi nhiều khách cùng mở trang này.
    # paginate() chỉ tải đúng 1 trang (24 sản phẩm), nhẹ hơn rất nhiều và phản hồi nhanh
    # hơn hẳn dù có bao nhiêu sản phẩm trong catalog.
    pagination = query.paginate(page=page, per_page=PRODUCTS_PER_PAGE, error_out=False)
    products = pagination.items
    categories = get_cached_categories()

    # Hỗ trợ AJAX load nhanh không reload cả trang
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.args.get('ajax') == '1':
        return render_template(
            '_product_list_partial.html',
            products=products,
            pagination=pagination,
            search_query=q,
            selected_category=category_id
        )

    return render_template('products.html', products=products, pagination=pagination,
                            categories=categories, selected_category=category_id, search_query=q)


# ============================================
#   KHÁCH HÀNG - ĐĂNG KÝ / ĐĂNG NHẬP / ĐĂNG XUẤT
#   (đăng nhập bằng số điện thoại + mật khẩu, tách biệt với tài khoản Admin)
# ============================================

def get_reset_serializer():
    return URLSafeTimedSerializer(app.config['SECRET_KEY'])


def send_password_reset_email(to_email, reset_url, verification_code):
    """Gửi mã xác thực và liên kết đặt lại mật khẩu qua SMTP."""
    mail_username = app.config.get('MAIL_USERNAME')
    mail_password = app.config.get('MAIL_PASSWORD')
    configured_sender = app.config.get('MAIL_DEFAULT_SENDER', '').strip()
    configured_sender_email = parseaddr(configured_sender)[1]
    sender_email = configured_sender_email or mail_username
    sender = configured_sender if configured_sender_email else f'Lego Flower <{sender_email}>'

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 580px; margin: 0 auto; padding: 28px; border: 1.5px solid #C9A227; border-radius: 16px; background: #ffffff;">
        <div style="text-align: center; margin-bottom: 24px;">
            <h2 style="color: #21243D; margin: 0 0 6px 0; font-size: 24px;">Lego Flower</h2>
            <p style="color: #6c757d; font-size: 14px; margin: 0;">Khôi phục mật khẩu tài khoản</p>
        </div>
        <p style="color: #333333; font-size: 15px; line-height: 1.6;">Xin chào,</p>
        <p style="color: #333333; font-size: 15px; line-height: 1.6;">Chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản Lego Flower liên kết với địa chỉ email <strong>{to_email}</strong>.</p>
        <p style="color: #333333; font-size: 15px; line-height: 1.6;">Mã xác thực của bạn là:</p>
        <div style="text-align: center; margin: 20px 0; font-size: 30px; font-weight: bold; letter-spacing: 8px; color: #21243D;">{verification_code}</div>
        <p style="color: #333333; font-size: 15px; line-height: 1.6;">Nhập mã này tại trang đặt lại mật khẩu. Mã và liên kết có hiệu lực trong vòng 30 phút.</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" style="display: inline-block; background: #C9A227; color: #ffffff; text-decoration: none; padding: 12px 30px; border-radius: 10px; font-weight: bold; font-size: 15px; letter-spacing: 0.3px;">Đặt lại mật khẩu</a>
        </div>
        <p style="color: #6c757d; font-size: 13px; line-height: 1.6;">Nếu nút trên không hoạt động, bạn có thể sao chép liên kết sau và dán vào thanh địa chỉ trình duyệt:<br>
            <a href="{reset_url}" style="color: #C9A227; word-break: break-all;">{reset_url}</a>
        </p>
        <p style="color: #8c857b; font-size: 13px; line-height: 1.5; margin-top: 24px;">
            <em>Nếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này. Mật khẩu của bạn vẫn an toàn.</em>
        </p>
        <hr style="border: none; border-top: 1px solid #eeeeee; margin: 24px 0 16px 0;">
        <p style="color: #aaaaaa; font-size: 12px; text-align: center; margin: 0;">Lego Flower Shop &bull; Shop hoa Lego nghệ thuật cao cấp</p>
    </div>
    """

    if not mail_username or not mail_password:
        return False, 'Chưa cấu hình MAIL_USERNAME và MAIL_PASSWORD.'

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "[Lego Flower] Đặt lại mật khẩu tài khoản"
        msg['From'] = sender
        msg['To'] = to_email
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        with smtplib.SMTP(app.config.get('MAIL_SERVER'), app.config.get('MAIL_PORT'), timeout=10) as server:
            server.ehlo()
            if app.config.get('MAIL_USE_TLS'):
                server.starttls()
                server.ehlo()
            server.login(mail_username, mail_password)
            server.sendmail(sender_email, [to_email], msg.as_string())
        return True, "sent"
    except Exception as ex:
        print(f"[ERROR GỬI EMAIL] {ex}")
        return False, str(ex)


@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5 per minute, 15 per hour")  # chặn spam tạo tài khoản hàng loạt
def register():
    if current_user.is_authenticated and isinstance(current_user, Customer):
        return redirect(url_for('index'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        phone = normalize_phone(request.form.get('phone', ''))
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        errors = []
        if not full_name:
            errors.append('Vui lòng nhập họ tên.')
        if not phone or not PHONE_REGEX.match(phone):
            errors.append('Số điện thoại không hợp lệ. Số di động Việt Nam gồm đúng 10 chữ số (VD: 0912345678).')
        elif Customer.query.filter_by(phone=phone).first():
            errors.append('Số điện thoại này đã được đăng ký.')

        if not email:
            errors.append('Vui lòng nhập địa chỉ email.')
        elif not EMAIL_REGEX.match(email):
            errors.append('Địa chỉ email không đúng định dạng (VD: example@gmail.com).')
        elif Customer.query.filter(func.lower(Customer.email) == email).first():
            errors.append('Địa chỉ email này đã được sử dụng.')

        if len(password) < 6:
            errors.append('Mật khẩu phải có ít nhất 6 ký tự.')
        elif password != password2:
            errors.append('Mật khẩu nhập lại không khớp.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('register.html', full_name=full_name, phone=phone, email=email)

        customer = Customer(phone=phone, email=email, full_name=full_name[:100])
        customer.set_password(password)
        db.session.add(customer)
        db.session.commit()

        login_user(customer, remember=True)
        flash(f'Chào mừng {customer.full_name} đã tham gia Lego Flower!', 'success')
        return redirect(url_for('index'))

    return render_template('register.html')


@app.route('/review/<int:review_id>/delete', methods=['POST'])
@login_required
def delete_own_review(review_id):
    """Cho phép khách hàng xóa review CỦA CHÍNH MÌNH (khác route admin xóa review bất kỳ)."""
    review = Review.query.get_or_404(review_id)
    if not isinstance(current_user, Customer) or review.customer_id != current_user.id:
        abort(403)

    product_id = review.product_id
    db.session.delete(review)
    db.session.commit()
    flash('Đã xóa đánh giá của bạn.', 'success')

    next_url = request.form.get('next')
    if next_url and next_url.startswith('/'):
        return redirect(next_url)
    return redirect(url_for('product_detail', product_id=product_id) + '#reviews')


def process_and_save_avatar(file_storage, customer_id):
    """
    Xử lý ảnh đại diện của khách hàng:
    - Kiểm tra định dạng (png, jpg, jpeg, webp, gif)
    - Xoay đúng chiều theo EXIF camera
    - Cắt vuông chính giữa (center crop)
    - Resize về kích thước chuẩn 320x320
    - Lưu định dạng WEBP siêu nét và nhẹ (~30KB)
    - Trả về (tên_file, None) nếu thành công hoặc (None, lỗi)
    """
    if not file_storage or not file_storage.filename:
        return None, 'Chưa chọn tệp ảnh.'

    filename = file_storage.filename.lower()
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''
    allowed_exts = app.config.get('ALLOWED_AVATAR_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'webp'})
    if ext not in allowed_exts:
        return None, 'Định dạng ảnh không được hỗ trợ. Vui lòng chọn ảnh JPG, PNG, WEBP hoặc GIF.'

    try:
        img = Image.open(file_storage.stream)
        img = ImageOps.exif_transpose(img)

        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            img = img.convert('RGBA')
        else:
            img = img.convert('RGB')

        w, h = img.size
        min_dim = min(w, h)
        left = (w - min_dim) // 2
        top = (h - min_dim) // 2
        img = img.crop((left, top, left + min_dim, top + min_dim))
        img = img.resize((320, 320), Image.Resampling.LANCZOS)

        avatar_filename = f"avatar_{customer_id}_{int(time.time())}.webp"
        save_path = os.path.join(app.config['AVATAR_UPLOAD_FOLDER'], avatar_filename)
        img.save(save_path, format='WEBP', quality=88, method=6)
        return avatar_filename, None
    except Exception as e:
        return None, f'Không thể xử lý tệp ảnh: {str(e)}'


def remove_old_avatar(avatar_filename):
    """Xóa file ảnh đại diện cũ khỏi đĩa để giải phóng dung lượng."""
    if avatar_filename:
        try:
            old_path = os.path.join(app.config['AVATAR_UPLOAD_FOLDER'], avatar_filename)
            if os.path.exists(old_path):
                os.remove(old_path)
        except Exception:
            pass


@app.route('/settings', methods=['GET', 'POST'])
@customer_required
def user_settings():
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_avatar':
            avatar_file = request.files.get('avatar')
            if not avatar_file or not avatar_file.filename:
                flash('Vui lòng chọn một tệp ảnh để làm ảnh đại diện.', 'error')
            else:
                new_avatar, err = process_and_save_avatar(avatar_file, current_user.id)
                if err:
                    flash(err, 'error')
                else:
                    remove_old_avatar(current_user.avatar)
                    current_user.avatar = new_avatar
                    db.session.commit()
                    flash('Cập nhật ảnh đại diện thành công!', 'success')
            return redirect(url_for('user_settings'))

        elif action == 'delete_avatar':
            if current_user.avatar:
                remove_old_avatar(current_user.avatar)
                current_user.avatar = None
                db.session.commit()
                flash('Đã gỡ ảnh đại diện, chuyển về biểu tượng mặc định.', 'success')
            else:
                flash('Bạn hiện chưa cài đặt ảnh đại diện riêng.', 'info')
            return redirect(url_for('user_settings'))

        elif action == 'update_profile':
            full_name = request.form.get('full_name', '').strip()
            phone_raw = request.form.get('phone', '').strip()
            email = request.form.get('email', '').strip().lower()
            avatar_file = request.files.get('avatar')
            errors = []

            if not full_name:
                errors.append('Họ và tên không được để trống.')

            phone = normalize_phone(phone_raw)
            if not phone or not PHONE_REGEX.match(phone):
                errors.append('Số điện thoại không hợp lệ. Số di động Việt Nam gồm đúng 10 chữ số (VD: 0912345678).')
            else:
                existing_phone = Customer.query.filter(Customer.phone == phone, Customer.id != current_user.id).first()
                if existing_phone:
                    errors.append('Số điện thoại này đã được sử dụng bởi tài khoản khác.')

            if email:
                if not EMAIL_REGEX.match(email):
                    errors.append('Địa chỉ email không đúng định dạng.')
                else:
                    existing = Customer.query.filter(func.lower(Customer.email) == email, Customer.id != current_user.id).first()
                    if existing:
                        errors.append('Địa chỉ email này đã được sử dụng bởi tài khoản khác.')

            if errors:
                for e in errors:
                    flash(e, 'error')
            else:
                if avatar_file and avatar_file.filename:
                    new_avatar, err = process_and_save_avatar(avatar_file, current_user.id)
                    if err:
                        flash(err, 'error')
                    else:
                        remove_old_avatar(current_user.avatar)
                        current_user.avatar = new_avatar

                current_user.full_name = full_name[:100]
                current_user.phone = phone
                current_user.email = email or None
                db.session.commit()
                flash('Cập nhật thông tin thành công!', 'success')
            return redirect(url_for('user_settings'))

        elif action == 'change_password':
            current_pwd = request.form.get('current_password', '')
            new_pwd = request.form.get('new_password', '')
            confirm_pwd = request.form.get('confirm_password', '')

            if not current_user.check_password(current_pwd):
                flash('Mật khẩu hiện tại không chính xác.', 'error')
            elif len(new_pwd) < 6:
                flash('Mật khẩu mới phải có ít nhất 6 ký tự.', 'error')
            elif new_pwd != confirm_pwd:
                flash('Mật khẩu xác nhận không khớp.', 'error')
            else:
                current_user.set_password(new_pwd)
                db.session.commit()
                flash('Đổi mật khẩu thành công!', 'success')
            return redirect(url_for('user_settings') + '#password')

    my_reviews = Review.query.filter_by(customer_id=current_user.id).order_by(Review.created_at.desc()).all()
    my_orders = Order.query.filter_by(customer_id=current_user.id).order_by(Order.created_at.desc()).all()
    return render_template('user_settings.html', my_reviews=my_reviews, my_orders=my_orders)


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute, 25 per hour")  # chống brute-force đoán mật khẩu
def login():
    if current_user.is_authenticated and isinstance(current_user, Customer):
        return redirect(url_for('index'))

    if request.method == 'POST':
        identifier = request.form.get('login_identifier', '').strip()
        password = request.form.get('password', '')
        remember = bool(request.form.get('remember'))

        customer = None
        if '@' in identifier:
            customer = Customer.query.filter(func.lower(Customer.email) == identifier.lower()).first()
        else:
            phone = normalize_phone(identifier)
            customer = Customer.query.filter_by(phone=phone).first()

        if customer and customer.check_password(password):
            login_user(customer, remember=remember)
            next_page = request.args.get('next')
            if next_page and next_page.startswith('/'):
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            flash('Số điện thoại/Email hoặc mật khẩu không chính xác!', 'error')
            return render_template('login.html', login_identifier=identifier)

    return render_template('login.html')


@app.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit("3 per minute, 10 per hour")  # gửi email thật qua SMTP -> giới hạn chặt để tránh bị spam/khóa tài khoản mail
def forgot_password():
    if current_user.is_authenticated and isinstance(current_user, Customer):
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email or not EMAIL_REGEX.match(email):
            flash('Vui lòng nhập địa chỉ email hợp lệ.', 'error')
            return render_template('forgot_password.html', email=email)

        customer = Customer.query.filter(func.lower(Customer.email) == email).first()
        if customer:
            serializer = get_reset_serializer()
            verification_code = f'{secrets.randbelow(1_000_000):06d}'
            token = serializer.dumps(
                {'email': customer.email, 'code': verification_code},
                salt='password-reset-salt'
            )
            reset_url = url_for('reset_password', token=token, _external=True)
            sent, error = send_password_reset_email(customer.email, reset_url, verification_code)
            if not sent:
                app.logger.error('Không thể gửi email đặt lại mật khẩu cho %s: %s', customer.email, error)
                flash('Hệ thống chưa thể gửi mã xác thực. Vui lòng thử lại sau hoặc liên hệ cửa hàng.', 'error')
                return render_template('forgot_password.html', email=email)

        flash('Nếu email của bạn tồn tại trong hệ thống, chúng tôi đã gửi mã xác thực và liên kết đặt lại mật khẩu. Vui lòng kiểm tra hộp thư (kể cả mục Spam/Thư rác).', 'success')
        return redirect(url_for('login'))

    return render_template('forgot_password.html')


@app.route('/reset-password/<token>', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def reset_password(token):
    if current_user.is_authenticated and isinstance(current_user, Customer):
        return redirect(url_for('index'))

    serializer = get_reset_serializer()
    try:
        reset_payload = serializer.loads(token, salt='password-reset-salt', max_age=1800)
        # Hỗ trợ các liên kết cũ đã phát hành trước khi bổ sung mã xác thực.
        if isinstance(reset_payload, dict):
            email = reset_payload.get('email', '')
            expected_code = str(reset_payload.get('code', ''))
        else:
            email = str(reset_payload)
            expected_code = ''
    except SignatureExpired:
        flash('Liên kết đặt lại mật khẩu đã hết hạn (chỉ có hiệu lực trong 30 phút). Vui lòng yêu cầu lại.', 'error')
        return redirect(url_for('forgot_password'))
    except BadTimeSignature:
        flash('Liên kết đặt lại mật khẩu không hợp lệ.', 'error')
        return redirect(url_for('forgot_password'))

    customer = Customer.query.filter(func.lower(Customer.email) == email.lower()).first()
    if not customer:
        flash('Tài khoản không tồn tại.', 'error')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        verification_code = request.form.get('verification_code', '').strip()
        password = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        if expected_code and not hmac.compare_digest(verification_code, expected_code):
            flash('Mã xác thực không chính xác. Vui lòng kiểm tra lại email.', 'error')
            return render_template('reset_password.html', token=token, requires_code=True)
        if len(password) < 6:
            flash('Mật khẩu mới phải có ít nhất 6 ký tự.', 'error')
            return render_template('reset_password.html', token=token, requires_code=bool(expected_code))
        if password != password2:
            flash('Mật khẩu xác nhận không khớp.', 'error')
            return render_template('reset_password.html', token=token, requires_code=bool(expected_code))

        customer.set_password(password)
        db.session.commit()
        flash('Đặt lại mật khẩu thành công! Bạn có thể đăng nhập bằng mật khẩu mới ngay bây giờ.', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html', token=token, requires_code=bool(expected_code))


@app.route('/logout')
@login_required
def logout():
    if isinstance(current_user, Customer):
        logout_user()
    return redirect(url_for('index'))


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.options(
        selectinload(Product.media),
        selectinload(Product.reviews).selectinload(Review.customer),
        selectinload(Product.category)
    ).get_or_404(product_id)

    # Lấy tối đa 4 sản phẩm cùng danh mục gợi ý thêm (loại trừ sản phẩm hiện tại)
    related_products = []
    if product.category_id:
        related_products = Product.query.options(
            selectinload(Product.media),
            selectinload(Product.reviews)
        ).filter(
            Product.category_id == product.category_id,
            Product.id != product.id
        ).order_by(Product.id.desc()).limit(4).all()
    if not related_products:
        # Nếu danh mục này không còn sp khác, lấy 4 sp mới nhất khác
        related_products = Product.query.options(
            selectinload(Product.media),
            selectinload(Product.reviews)
        ).filter(Product.id != product.id).order_by(Product.id.desc()).limit(4).all()

    # Nếu khách hàng đã đăng nhập, kiểm tra xem họ đã đánh giá sản phẩm này chưa
    # (để ẩn form và hiện thông báo thay vì cho đánh giá trùng)
    my_review = None
    if current_user.is_authenticated and isinstance(current_user, Customer):
        my_review = Review.query.filter_by(customer_id=current_user.id, product_id=product.id).first()

    return render_template('product_detail.html', product=product,
                            related_products=related_products, my_review=my_review)


@app.route('/product/<int:product_id>/review', methods=['POST'])
@limiter.limit("6 per minute")  # chống spam review hàng loạt
def submit_review(product_id):
    # Đảm bảo sản phẩm tồn tại, nếu không sẽ tự trả về 404
    product = Product.query.get_or_404(product_id)

    is_logged_in_customer = current_user.is_authenticated and isinstance(current_user, Customer)

    # Nếu đã đăng nhập: lấy tên từ tài khoản, không tin vào tên tự nhập trên form
    # Nếu là khách vãng lai: vẫn cho phép nhập tên (giữ tương thích ngược)
    if is_logged_in_customer:
        customer_name = current_user.full_name
    else:
        customer_name = request.form.get('customer_name', '').strip()

    comment = request.form.get('comment', '').strip()
    rating_raw = request.form.get('rating', '')

    # Validate dữ liệu đầu vào - không tin tưởng dữ liệu người dùng gửi lên
    rating = None
    errors = []
    if not customer_name:
        errors.append('Vui lòng nhập tên của bạn.')
    try:
        rating = int(rating_raw)
        if rating < 1 or rating > 5:
            raise ValueError
    except (TypeError, ValueError):
        errors.append('Vui lòng chọn số sao từ 1 đến 5.')

    # Mỗi tài khoản khách hàng chỉ được đánh giá 1 lần / sản phẩm
    if is_logged_in_customer and Review.query.filter_by(
        customer_id=current_user.id, product_id=product.id
    ).first():
        errors.append('Bạn đã đánh giá sản phẩm này rồi.')

    if errors:
        for e in errors:
            flash(e, 'error')
        return redirect(url_for('product_detail', product_id=product_id) + '#reviews')

    review = Review(
        product_id=product.id,
        customer_id=current_user.id if is_logged_in_customer else None,
        customer_name=customer_name[:100],
        rating=rating,
        comment=comment or None
    )
    db.session.add(review)
    db.session.commit()
    flash('Cảm ơn bạn đã đánh giá sản phẩm!', 'success')
    return redirect(url_for('product_detail', product_id=product_id) + '#reviews')


# ============================================
#   GIỎ HÀNG (SHOPPING CART) & ĐẶT HÀNG (CHECKOUT)
# ============================================

@app.route('/cart')
def view_cart():
    """Xem trang giỏ hàng."""
    items, total_price, total_quantity = get_cart_details()
    return render_template('cart.html', items=items, total_price=total_price, total_quantity=total_quantity)


@app.route('/cart/add', methods=['POST'])
def cart_add():
    """Thêm sản phẩm vào giỏ hàng."""
    data = request.get_json(silent=True) or request.form
    try:
        product_id = int(data.get('product_id')) if data.get('product_id') is not None else None
    except (ValueError, TypeError):
        product_id = None
    try:
        quantity = int(data.get('quantity', 1)) if data.get('quantity') is not None else 1
    except (ValueError, TypeError):
        quantity = 1
    buy_now = data.get('buy_now')

    if not product_id or quantity <= 0:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Dữ liệu không hợp lệ'}), 400
        flash('Dữ liệu không hợp lệ', 'error')
        return redirect(request.referrer or url_for('products'))

    product = Product.query.get_or_404(product_id)
    if product.stock <= 0:
        if request.is_json:
            return jsonify({'success': False, 'error': 'Sản phẩm này tạm thời hết hàng'}), 400
        flash(f'Sản phẩm "{product.name}" tạm thời hết hàng.', 'warning')
        return redirect(request.referrer or url_for('products'))

    cart = session.get('cart', {})
    if not isinstance(cart, dict):
        cart = {}

    pid_str = str(product_id)
    current_qty = cart.get(pid_str, 0)
    new_qty = current_qty + quantity
    if new_qty > product.stock:
        new_qty = product.stock

    cart[pid_str] = new_qty
    session['cart'] = cart
    session.modified = True

    cart_count = sum(cart.values())

    if buy_now:
        return redirect(url_for('checkout'))

    items, total_price, total_quantity = get_cart_details()

    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'success': True,
            'cart_count': total_quantity,
            'message': f'Đã thêm {quantity} x "{product.name}" vào giỏ hàng!',
            'product_name': product.name,
            'product_price_str': f"{product.price:,.0f} đ",
            'thumbnail': url_for('static', filename='uploads/' + product.thumbnail) if product.thumbnail else None,
            'total_price': total_price,
            'total_price_str': f"{total_price:,.0f} đ"
        })

    flash(f'Đã thêm "{product.name}" vào giỏ hàng!', 'success')
    return redirect(request.referrer or url_for('view_cart'))


@app.route('/cart/update', methods=['POST'])
def cart_update():
    """Cập nhật số lượng sản phẩm trong giỏ hàng."""
    data = request.get_json(silent=True) or request.form
    try:
        product_id = int(data.get('product_id')) if data.get('product_id') is not None else None
    except (ValueError, TypeError):
        product_id = None
    try:
        quantity = int(data.get('quantity')) if data.get('quantity') is not None else 0
    except (ValueError, TypeError):
        quantity = 0

    if not product_id:
        return jsonify({'success': False, 'error': 'Thiếu ID sản phẩm'}), 400

    cart = session.get('cart', {})
    if not isinstance(cart, dict):
        cart = {}

    pid_str = str(product_id)
    product = Product.query.get(product_id)

    max_reached = False
    if quantity is None or quantity <= 0:
        cart.pop(pid_str, None)
    else:
        if product and quantity > product.stock:
            quantity = product.stock
            max_reached = True
        cart[pid_str] = quantity

    session['cart'] = cart
    session.modified = True

    items, total_price, total_quantity = get_cart_details()

    if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        item_subtotal = 0
        if product and pid_str in cart:
            item_subtotal = product.price * cart[pid_str]
        return jsonify({
            'success': True,
            'cart_count': total_quantity,
            'item_subtotal': item_subtotal,
            'item_subtotal_str': f"{item_subtotal:,.0f} đ",
            'total_price': total_price,
            'total_price_str': f"{total_price:,.0f} đ",
            'total_quantity': total_quantity,
            'quantity': cart.get(pid_str, 0),
            'max_reached': max_reached,
            'available_stock': product.stock if product else 0
        })

    return redirect(url_for('view_cart'))


@app.route('/cart/remove/<int:product_id>', methods=['POST'])
def cart_remove(product_id):
    """Xóa sản phẩm khỏi giỏ hàng."""
    cart = session.get('cart', {})
    if isinstance(cart, dict):
        cart.pop(str(product_id), None)
        session['cart'] = cart
        session.modified = True
    flash('Đã xóa sản phẩm khỏi giỏ hàng.', 'info')
    return redirect(url_for('view_cart'))


@app.route('/cart/clear', methods=['POST'])
def cart_clear():
    """Xóa toàn bộ giỏ hàng."""
    session.pop('cart', None)
    session.modified = True
    flash('Đã xóa toàn bộ giỏ hàng.', 'info')
    return redirect(url_for('view_cart'))


@app.route('/checkout', methods=['GET', 'POST'])
@limiter.limit("10 per minute")  # Chống flood tạo đơn hàng ảo liên tục
def checkout():
    """Trang thanh toán / xác nhận đặt hàng."""
    items, total_price, total_quantity = get_cart_details()
    if not items or total_quantity == 0:
        flash('Giỏ hàng của bạn đang trống. Vui lòng chọn sản phẩm trước khi đặt hàng!', 'warning')
        return redirect(url_for('products'))

    if request.method == 'POST':
        customer_name = (request.form.get('customer_name') or '').strip()
        customer_phone = (request.form.get('customer_phone') or '').strip()
        shipping_address = (request.form.get('shipping_address') or '').strip()
        delivery_time = (request.form.get('delivery_time') or 'Giao sớm nhất có thể').strip()
        customer_note = (request.form.get('customer_note') or '').strip()

        if not customer_name or not customer_phone or not shipping_address:
            flash('Vui lòng điền đầy đủ Họ tên, Số điện thoại và Địa chỉ nhận hàng!', 'error')
            return render_template('checkout.html', items=items, total_price=total_price, total_quantity=total_quantity)

        customer_phone = normalize_phone(customer_phone)
        if not PHONE_REGEX.match(customer_phone):
            flash('Số điện thoại không hợp lệ. Vui lòng nhập số điện thoại 10 chữ số (VD: 0912345678).', 'error')
            return render_template('checkout.html', items=items, total_price=total_price, total_quantity=total_quantity)

        # Kiểm tra tồn kho lần cuối
        for item in items:
            p = item['product']
            qty = item['quantity']
            if p.stock < qty:
                flash(f'Sản phẩm "{p.name}" chỉ còn {p.stock} bó trong kho. Vui lòng giảm số lượng!', 'error')
                return redirect(url_for('view_cart'))

        order_code = generate_order_code()
        while Order.query.filter_by(order_code=order_code).first():
            order_code = generate_order_code()

        customer_id = None
        if current_user.is_authenticated and isinstance(current_user, Customer):
            customer_id = current_user.id

        order = Order(
            order_code=order_code,
            customer_id=customer_id,
            customer_name=customer_name,
            customer_phone=customer_phone,
            shipping_address=shipping_address,
            delivery_time=delivery_time,
            customer_note=customer_note,
            total_price=total_price,
            status='pending',
            payment_status='contact_later'
        )
        db.session.add(order)
        db.session.flush()

        for item in items:
            p = item['product']
            qty = item['quantity']
            p.stock -= qty

            order_item = OrderItem(
                order_id=order.id,
                product_id=p.id,
                product_name=p.name,
                product_price=p.price,
                quantity=qty,
                subtotal=item['subtotal'],
                product_image=p.thumbnail
            )
            db.session.add(order_item)

        db.session.commit()

        session.pop('cart', None)
        session.modified = True

        return redirect(url_for('order_success', order_code=order_code))

    default_name = ''
    default_phone = ''
    if current_user.is_authenticated and isinstance(current_user, Customer):
        default_name = current_user.full_name or ''
        default_phone = current_user.phone or ''

    return render_template(
        'checkout.html',
        items=items,
        total_price=total_price,
        total_quantity=total_quantity,
        default_name=default_name,
        default_phone=default_phone
    )


@app.route('/order-success/<order_code>')
def order_success(order_code):
    """Trang thông báo đặt hàng thành công."""
    order = Order.query.filter_by(order_code=order_code).first_or_404()
    return render_template('order_success.html', order=order)


@app.route('/orders', methods=['GET', 'POST'])
def my_orders_view():
    """Trang xem & tra cứu đơn hàng của bạn (dành cho cả khách đã đăng nhập và khách vãng lai)."""
    search_query = ''
    status_filter = request.args.get('status', '').strip()

    if current_user.is_authenticated and isinstance(current_user, Customer):
        # Khách đã đăng nhập: hiển thị toàn bộ đơn hàng của tài khoản
        query = Order.query.filter_by(customer_id=current_user.id).options(selectinload(Order.items))
        if status_filter:
            query = query.filter_by(status=status_filter)
        q = request.args.get('q', '').strip()
        if q:
            search_query = q
            query = query.filter(Order.order_code.ilike(f'%{q}%'))
        orders = query.order_by(Order.created_at.desc()).all()
        lookup_mode = 'account'
    else:
        # Khách vãng lai / chưa đăng nhập: tra cứu qua SĐT hoặc mã đơn
        lookup_mode = 'guest'
        orders = []
        identifier = ''
        if request.method == 'POST':
            identifier = request.form.get('identifier', '').strip()
        else:
            identifier = request.args.get('identifier', '').strip()

        if identifier:
            search_query = identifier
            norm_phone = normalize_phone(identifier)

            # Nếu nhập đúng mã đơn hàng, chuyển thẳng tới trang chi tiết theo dõi
            if identifier.upper().startswith('LF'):
                exact_order = Order.query.filter(func.upper(Order.order_code) == identifier.upper()).first()
                if exact_order:
                    return redirect(url_for('order_detail', order_code=exact_order.order_code))

            query = Order.query.options(selectinload(Order.items))
            if norm_phone and PHONE_REGEX.match(norm_phone):
                query = query.filter(Order.customer_phone == norm_phone)
            else:
                query = query.filter((Order.order_code.ilike(f'%{identifier}%')) | (Order.customer_phone == identifier))

            if status_filter:
                query = query.filter_by(status=status_filter)
            orders = query.order_by(Order.created_at.desc()).all()
            if not orders:
                flash(f'Không tìm thấy đơn hàng nào khớp với thông tin "{identifier}". Vui lòng kiểm tra lại Số điện thoại hoặc Mã đơn hàng!', 'warning')

    return render_template(
        'orders.html',
        orders=orders,
        status_filter=status_filter,
        search_query=search_query,
        lookup_mode=lookup_mode
    )


@app.route('/order/<order_code>')
def order_detail(order_code):
    """Trang chi tiết & theo dõi tiến trình đơn hàng."""
    order = Order.query.options(selectinload(Order.items)).filter_by(order_code=order_code).first_or_404()
    return render_template('order_detail.html', order=order)


@app.route('/order/<order_code>/cancel', methods=['POST'])
@limiter.limit("10 per minute")
def order_cancel_customer(order_code):
    """Khách hàng tự hủy đơn hàng khi đơn còn ở trạng thái Chờ xác nhận."""
    order = Order.query.filter_by(order_code=order_code).first_or_404()
    if not order.can_cancel:
        flash('Đơn hàng đã được xác nhận hoặc đang giao nên không thể tự hủy trực tiếp. Vui lòng liên hệ shop qua Zalo/Hotline để được hỗ trợ!', 'warning')
        return redirect(request.referrer or url_for('order_detail', order_code=order_code))

    cancel_reason = (request.form.get('cancel_reason') or 'Khách hàng yêu cầu hủy đơn qua website').strip()
    order.status = 'cancelled'
    order.cancel_reason = cancel_reason

    # Hoàn lại số lượng tồn kho
    for item in order.items:
        if item.product:
            item.product.stock += item.quantity

    db.session.commit()
    flash(f'Đã hủy thành công đơn hàng #{order.order_code}. Số lượng hoa đã được hoàn trả lại kho.', 'success')
    return redirect(request.referrer or url_for('order_detail', order_code=order_code))


@app.route('/order/<order_code>/reorder', methods=['POST'])
@limiter.limit("15 per minute")
def order_reorder(order_code):
    """Mua lại / Đặt lại toàn bộ sản phẩm của đơn hàng cũ vào giỏ."""
    order = Order.query.options(selectinload(Order.items)).filter_by(order_code=order_code).first_or_404()
    cart = session.get('cart', {})
    if not isinstance(cart, dict):
        cart = {}

    added_count = 0
    for item in order.items:
        if item.product and item.product.stock > 0:
            pid_str = str(item.product.id)
            current_qty = cart.get(pid_str, 0)
            new_qty = min(current_qty + item.quantity, item.product.stock)
            cart[pid_str] = new_qty
            added_count += 1

    session['cart'] = cart
    session.modified = True

    if added_count > 0:
        flash(f'Đã thêm các món từ đơn #{order.order_code} vào giỏ hàng của bạn!', 'success')
    else:
        flash('Rất tiếc, các mẫu hoa trong đơn này hiện đang tạm hết hàng.', 'warning')

    return redirect(url_for('view_cart'))


# ============================================
#   ADMIN - LOGIN / LOGOUT
# ============================================

@app.route('/admin')
@app.route('/admin/')
def admin_root():
    """Tự động chuyển hướng /admin sang dashboard hoặc trang đăng nhập."""
    if current_user.is_authenticated and isinstance(current_user, Admin):
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('admin_login'))


@app.route('/admin/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute, 20 per hour")  # chống brute-force đoán mật khẩu admin
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        admin = Admin.query.filter_by(username=username).first()

        if admin and admin.check_password(password):
            login_user(admin)
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Sai tên đăng nhập hoặc mật khẩu!', 'error')

    return render_template('admin/login.html')


@app.route('/admin/logout')
@admin_required
def admin_logout():
    logout_user()
    return redirect(url_for('admin_login'))


# ============================================
#   ADMIN - QUẢN LÝ SẢN PHẨM (CRUD)
# ============================================

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    q = request.args.get('q', '').strip()
    category_id = request.args.get('category', type=int)

    query = Product.query.options(
        selectinload(Product.media),
        selectinload(Product.category)
    )
    if category_id:
        query = query.filter_by(category_id=category_id)
    if q:
        query = query.filter(Product.name.ilike(f'%{q}%'))

    products = query.order_by(Product.id.desc()).all()
    categories = get_cached_categories()
    return render_template(
        'admin/dashboard.html',
        products=products,
        categories=categories,
        search_query=q,
        selected_category=category_id
    )


@app.route('/admin/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    categories = get_cached_categories()

    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        description = request.form.get('description')
        stock = request.form.get('stock', 0)
        category_id = request.form.get('category_id') or None

        new_product = Product(
            name=name,
            price=float(price),
            description=description,
            stock=int(stock),
            category_id=category_id
        )
        db.session.add(new_product)
        db.session.flush()  # để có new_product.id trước khi lưu file

        # Lưu nhiều ảnh/video cùng lúc
        media_files = request.files.getlist('media')
        for media in save_media_files(media_files, new_product.id):
            db.session.add(media)

        db.session.commit()
        flash('Đã thêm sản phẩm thành công!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/add_product.html', categories=categories)


@app.route('/admin/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    product = Product.query.get_or_404(product_id)
    categories = get_cached_categories()

    if request.method == 'POST':
        product.name = request.form.get('name')
        product.price = float(request.form.get('price'))
        product.description = request.form.get('description')
        product.stock = int(request.form.get('stock', 0))
        product.category_id = request.form.get('category_id') or None

        # Thêm ảnh/video mới (không xóa ảnh cũ, xóa riêng qua nút Xóa ở từng ảnh)
        media_files = request.files.getlist('media')
        for media in save_media_files(media_files, product.id):
            db.session.add(media)

        db.session.commit()
        flash('Đã cập nhật sản phẩm!', 'success')
        return redirect(url_for('admin_dashboard'))

    return render_template('admin/edit_product.html', product=product, categories=categories)


@app.route('/admin/media/delete/<int:media_id>', methods=['POST'])
@admin_required
def admin_delete_media(media_id):
    media = ProductMedia.query.get_or_404(media_id)
    product_id = media.product_id
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], media.filename)
    if os.path.exists(filepath):
        os.remove(filepath)
    db.session.delete(media)
    db.session.commit()
    flash('Đã xóa ảnh/video!', 'success')
    return redirect(url_for('admin_edit_product', product_id=product_id))


@app.route('/admin/review/delete/<int:review_id>', methods=['POST'])
@admin_required
def admin_delete_review(review_id):
    # Cho phép admin xóa các đánh giá spam / không phù hợp
    review = Review.query.get_or_404(review_id)
    product_id = review.product_id
    db.session.delete(review)
    db.session.commit()
    flash('Đã xóa đánh giá!', 'success')
    return redirect(url_for('product_detail', product_id=product_id))


@app.route('/admin/delete/<int:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    product = Product.query.get_or_404(product_id)

    # 1. Xóa toàn bộ file ảnh / video liên quan trong thư mục static/uploads
    for m in product.media:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], m.filename)
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError:
                pass

    if product.image:
        old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], product.image)
        if os.path.exists(old_filepath):
            try:
                os.remove(old_filepath)
            except OSError:
                pass

    # 2. Xóa bản ghi trong database
    db.session.delete(product)
    db.session.commit()
    flash('Đã xóa sản phẩm thành công!', 'success')
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/delete_multiple', methods=['POST'])
@admin_required
def admin_delete_multiple():
    product_ids = request.form.getlist('product_ids')
    if not product_ids:
        flash('Chưa chọn sản phẩm nào để xóa!', 'error')
        return redirect(url_for('admin_dashboard'))

    deleted_count = 0
    for pid in product_ids:
        try:
            product = Product.query.get(int(pid))
            if product:
                # Xóa toàn bộ file ảnh / video liên quan trong thư mục static/uploads
                for m in product.media:
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], m.filename)
                    if os.path.exists(filepath):
                        try:
                            os.remove(filepath)
                        except OSError:
                            pass

                if product.image:
                    old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], product.image)
                    if os.path.exists(old_filepath):
                        try:
                            os.remove(old_filepath)
                        except OSError:
                            pass

                db.session.delete(product)
                deleted_count += 1
        except Exception as e:
            print(f"Lỗi khi xóa sản phẩm {pid}: {e}")

    db.session.commit()
    flash(f'Đã xóa thành công {deleted_count} sản phẩm!', 'success')
    return redirect(url_for('admin_dashboard'))


# ============================================
#   ADMIN - QUẢN LÝ DANH MỤC (CRUD)
# ============================================

@app.route('/admin/categories')
@admin_required
def admin_categories():
    categories = get_cached_categories()
    return render_template('admin/categories.html', categories=categories)


@app.route('/admin/categories/add', methods=['GET', 'POST'])
@admin_required
def admin_add_category():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if name:
            db.session.add(Category(name=name))
            db.session.commit()
            invalidate_categories_cache()
            flash('Đã thêm danh mục!', 'success')
        else:
            flash('Tên danh mục không được để trống!', 'error')
        return redirect(url_for('admin_categories'))
    return render_template('admin/add_category.html')


@app.route('/admin/categories/edit/<int:category_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_category(category_id):
    category = Category.query.get_or_404(category_id)
    if request.method == 'POST':
        category.name = request.form.get('name', '').strip()
        db.session.commit()
        invalidate_categories_cache()
        flash('Đã cập nhật danh mục!', 'success')
        return redirect(url_for('admin_categories'))
    return render_template('admin/edit_category.html', category=category)


@app.route('/admin/categories/delete/<int:category_id>', methods=['POST'])
@admin_required
def admin_delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    # Sản phẩm thuộc danh mục này sẽ chuyển về "không có danh mục" thay vì bị xóa theo
    for product in category.products:
        product.category_id = None
    db.session.delete(category)
    db.session.commit()
    invalidate_categories_cache()
    flash('Đã xóa danh mục!', 'success')
    return redirect(url_for('admin_categories'))


# ============================================
#   ADMIN - QUẢN LÝ ĐƠN HÀNG (ORDERS)
# ============================================

@app.route('/admin/orders')
@admin_required
def admin_orders():
    """Trang quản lý đơn hàng của Admin."""
    status_filter = request.args.get('status', '').strip()
    q = request.args.get('q', '').strip()

    query = Order.query.options(
        selectinload(Order.customer),
        selectinload(Order.items).selectinload(OrderItem.product).selectinload(Product.media)
    )
    if status_filter:
        query = query.filter(Order.status == status_filter)
    if q:
        search_pat = f"%{q}%"
        query = query.filter(
            (Order.order_code.ilike(search_pat)) |
            (Order.customer_name.ilike(search_pat)) |
            (Order.customer_phone.ilike(search_pat))
        )

    orders = query.order_by(Order.created_at.desc()).all()

    # Tối ưu: thay vì 6 câu COUNT riêng (tốn 6 query DB), chỉ dùng 1 câu GROUP BY
    status_counts = db.session.query(Order.status, func.count(Order.id)).group_by(Order.status).all()
    status_count_map = {s: c for s, c in status_counts}
    counts = {
        'all': sum(status_count_map.values()),
        'pending': status_count_map.get('pending', 0),
        'confirmed': status_count_map.get('confirmed', 0),
        'shipping': status_count_map.get('shipping', 0),
        'completed': status_count_map.get('completed', 0),
        'cancelled': status_count_map.get('cancelled', 0),
    }

    return render_template('admin/orders.html', orders=orders, status_filter=status_filter, q=q, counts=counts)


@app.route('/admin/orders/<int:order_id>/status', methods=['POST'])
@admin_required
def admin_order_update_status(order_id):
    """Admin cập nhật trạng thái đơn hàng."""
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('status')
    valid_statuses = ['pending', 'confirmed', 'shipping', 'completed', 'cancelled']
    if new_status in valid_statuses:
        old_status = order.status
        order.status = new_status

        # Nếu hủy đơn -> hoàn lại tồn kho
        if new_status == 'cancelled' and old_status != 'cancelled':
            for item in order.items:
                if item.product:
                    item.product.stock += item.quantity
        # Nếu mở lại đơn từ hủy -> trừ lại tồn kho
        elif old_status == 'cancelled' and new_status != 'cancelled':
            for item in order.items:
                if item.product:
                    item.product.stock = max(0, item.product.stock - item.quantity)

        db.session.commit()
        flash(f'Đã cập nhật trạng thái đơn #{order.order_code} thành "{order.status_label}"!', 'success')
    return redirect(request.referrer or url_for('admin_orders'))


@app.route('/admin/orders/<int:order_id>/delete', methods=['POST'])
@admin_required
def admin_order_delete(order_id):
    """Admin xóa đơn hàng."""
    order = Order.query.get_or_404(order_id)
    # Nếu đơn chưa hoàn thành và chưa hủy, hoàn lại tồn kho
    if order.status not in ('completed', 'cancelled'):
        for item in order.items:
            if item.product:
                item.product.stock += item.quantity
    db.session.delete(order)
    db.session.commit()
    flash(f'Đã xóa đơn hàng #{order.order_code} thành công!', 'success')
    return redirect(url_for('admin_orders'))


# ============================================
#   HỆ THỐNG LIVE CHAT TRỰC TIẾP KHÁCH - ADMIN
# ============================================

@app.route('/api/chat/send', methods=['POST'])
@limiter.limit("20 per minute")  # chống flood tin nhắn chat
def api_chat_send():
    """Khách hàng gửi tin nhắn lên server."""
    data = request.get_json(silent=True) or request.form
    session_id = (data.get('session_id') or '').strip()
    message = (data.get('message') or '').strip()
    prev_guest_session = (data.get('prev_guest_session') or '').strip()

    if not session_id:
        return jsonify({'error': 'Thiếu session_id'}), 400
    if not message:
        return jsonify({'error': 'Tin nhắn không được để trống'}), 400
    if len(message) > 2000:
        return jsonify({'error': 'Tin nhắn quá dài (tối đa 2000 ký tự)'}), 400

    customer_id = None
    sender_name = 'Khách vãng lai'

    if current_user.is_authenticated and isinstance(current_user, Customer):
        customer_id = current_user.id
        sender_name = current_user.full_name or f'Khách hàng #{current_user.id}'
        canonical_session = f'cust_{customer_id}'

        # Gộp tất cả tin nhắn từ phiên cũ (nếu có) sang canonical session để không bị tách đoạn chat
        sessions_to_merge = [s for s in [session_id, prev_guest_session] if s and s != canonical_session]
        if sessions_to_merge:
            ChatMessage.query.filter(ChatMessage.session_id.in_(sessions_to_merge)).update({
                'session_id': canonical_session,
                'customer_id': customer_id,
                'sender_name': sender_name
            }, synchronize_session=False)

        # Đảm bảo toàn bộ tin nhắn trước đây của khách này đều thuộc canonical session
        ChatMessage.query.filter(
            ChatMessage.customer_id == customer_id,
            ChatMessage.session_id != canonical_session
        ).update({'session_id': canonical_session}, synchronize_session=False)

        session_id = canonical_session

    msg = ChatMessage(
        session_id=session_id,
        customer_id=customer_id,
        sender_type='customer',
        sender_name=sender_name,
        message=message,
        is_read=False
    )
    db.session.add(msg)
    db.session.commit()

    return jsonify({'success': True, 'message': msg.to_dict()})


@app.route('/api/chat/messages', methods=['GET'])
@limiter.limit("60 per minute")  # dư sức cho polling bình thường, chặn script spam
def api_chat_messages():
    """Khách hàng lấy danh sách tin nhắn của phiên chat hiện tại."""
    session_id = (request.args.get('session_id') or '').strip()
    after_id = request.args.get('after_id', 0, type=int)

    if not session_id:
        return jsonify({'error': 'Thiếu session_id'}), 400

    if current_user.is_authenticated and isinstance(current_user, Customer):
        canonical_session = f'cust_{current_user.id}'
        if session_id != canonical_session:
            ChatMessage.query.filter_by(session_id=session_id).update({
                'session_id': canonical_session,
                'customer_id': current_user.id,
                'sender_name': current_user.full_name or f'Khách hàng #{current_user.id}'
            }, synchronize_session=False)
            db.session.commit()
        session_id = canonical_session

    query = ChatMessage.query.filter_by(session_id=session_id)
    if after_id > 0:
        query = query.filter(ChatMessage.id > after_id)

    msgs = query.order_by(ChatMessage.id.asc()).all()

    # Đánh dấu các tin nhắn của Admin gửi cho khách này là đã đọc (chỉ commit khi thực sự có tin mới chưa đọc)
    if any(m.sender_type == 'admin' and not m.is_read for m in msgs):
        ChatMessage.query.filter_by(session_id=session_id, sender_type='admin', is_read=False).update({'is_read': True})
        db.session.commit()

    return jsonify({'messages': [m.to_dict() for m in msgs]})


@app.route('/admin/chat')
@admin_required
def admin_chat():
    """Giao diện quản lý tin nhắn và chat trực tiếp với khách hàng của Admin."""
    return render_template('admin/chat.html')


@app.route('/api/admin/chat/conversations')
@admin_required
def api_admin_chat_conversations():
    """Lấy danh sách các cuộc trò chuyện từ tất cả khách hàng (tối ưu hóa batch query)."""
    subquery = db.session.query(
        ChatMessage.session_id,
        func.max(ChatMessage.id).label('max_id')
    ).group_by(ChatMessage.session_id).subquery()

    latest_messages = db.session.query(ChatMessage).join(
        subquery,
        ChatMessage.id == subquery.c.max_id
    ).options(selectinload(ChatMessage.customer)).order_by(ChatMessage.id.desc()).all()

    # Tính toán số tin chưa đọc trong 1 câu query duy nhất (thay vì lặp N câu query)
    unread_map = dict(
        db.session.query(ChatMessage.session_id, func.count(ChatMessage.id))
        .filter(ChatMessage.sender_type == 'customer', ChatMessage.is_read == False)
        .group_by(ChatMessage.session_id)
        .all()
    )

    conversations = []
    for msg in latest_messages:
        unread = unread_map.get(msg.session_id, 0)
        cust = msg.customer
        if not cust and msg.session_id.startswith('cust_'):
            try:
                cid = int(msg.session_id.replace('cust_', ''))
                cust = db.session.get(Customer, cid)
            except Exception:
                pass

        cust_info = {
            'id': cust.id if cust else None,
            'name': cust.full_name if cust else msg.sender_name,
            'phone': cust.phone if cust else '',
            'email': cust.email if cust else '',
            'avatar': cust.avatar if cust else None,
            'is_member': bool(cust)
        }

        conversations.append({
            'session_id': msg.session_id,
            'customer': cust_info,
            'last_message': msg.message,
            'last_time': msg.created_at.strftime('%H:%M %d/%m'),
            'sender_type': msg.sender_type,
            'unread_count': unread
        })

    return jsonify({'conversations': conversations})


@app.route('/api/admin/chat/messages/<session_id>')
@admin_required
def api_admin_chat_messages(session_id):
    """Lấy toàn bộ tin nhắn trong một cuộc trò chuyện và đánh dấu đã đọc."""
    cust_id = None
    if session_id.startswith('cust_'):
        try:
            cust_id = int(session_id.replace('cust_', ''))
        except Exception:
            pass

    if cust_id:
        msgs = ChatMessage.query.filter(
            or_(ChatMessage.session_id == session_id, ChatMessage.customer_id == cust_id)
        ).order_by(ChatMessage.id.asc()).all()
        ChatMessage.query.filter(
            ChatMessage.customer_id == cust_id,
            ChatMessage.session_id != session_id
        ).update({'session_id': session_id}, synchronize_session=False)
        ChatMessage.query.filter(
            or_(ChatMessage.session_id == session_id, ChatMessage.customer_id == cust_id),
            ChatMessage.sender_type == 'customer',
            ChatMessage.is_read == False
        ).update({'is_read': True}, synchronize_session=False)
    else:
        msgs = ChatMessage.query.filter_by(session_id=session_id).order_by(ChatMessage.id.asc()).all()
        ChatMessage.query.filter_by(
            session_id=session_id,
            sender_type='customer',
            is_read=False
        ).update({'is_read': True})
    db.session.commit()

    cust = None
    if cust_id:
        cust = db.session.get(Customer, cust_id)
    if not cust:
        first_cust_msg = next((m for m in msgs if m.customer_id), None)
        cust = first_cust_msg.customer if first_cust_msg else None

    cust_info = {
        'id': cust.id if cust else None,
        'name': cust.full_name if cust else (msgs[0].sender_name if msgs else 'Khách vãng lai'),
        'phone': cust.phone if cust else '',
        'email': cust.email if cust else '',
        'avatar': cust.avatar if cust else None,
        'is_member': bool(cust),
        'created_at': cust.created_at.strftime('%d/%m/%Y') if cust else ''
    }

    return jsonify({
        'messages': [m.to_dict() for m in msgs],
        'customer': cust_info
    })


@app.route('/api/admin/chat/reply', methods=['POST'])
@admin_required
def api_admin_chat_reply():
    """Admin trả lời tin nhắn của một khách hàng."""
    data = request.get_json(silent=True) or request.form
    session_id = (data.get('session_id') or '').strip()
    message = (data.get('message') or '').strip()

    if not session_id or not message:
        return jsonify({'error': 'Thiếu session_id hoặc nội dung tin nhắn'}), 400

    cust_id = None
    if session_id.startswith('cust_'):
        try:
            cust_id = int(session_id.replace('cust_', ''))
        except Exception:
            pass

    if not cust_id:
        last_msg = ChatMessage.query.filter_by(session_id=session_id).first()
        cust_id = last_msg.customer_id if last_msg else None

    reply_msg = ChatMessage(
        session_id=session_id,
        customer_id=cust_id,
        sender_type='admin',
        sender_name=getattr(current_user, 'username', 'Quản trị viên'),
        message=message,
        is_read=False
    )
    db.session.add(reply_msg)
    db.session.commit()

    return jsonify({'success': True, 'message': reply_msg.to_dict()})


@app.route('/api/admin/chat/unread_count')
@admin_required
def api_admin_chat_unread_count():
    """Lấy tổng số tin nhắn chưa đọc từ khách hàng cho huy hiệu Admin."""
    unread_count = ChatMessage.query.filter_by(sender_type='customer', is_read=False).count()
    return jsonify({'unread_count': unread_count})


# ============================================
#   XỬ LÝ LỖI BẢO MẬT & TRẢ VỀ TRANG LỖI AN TOÀN
# ============================================

@app.errorhandler(400)
def handle_error_400(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Yêu cầu không hợp lệ'}), 400
    return render_template('error.html', code=400, title='Yêu cầu không hợp lệ', message='Yêu cầu gửi lên máy chủ không đúng định dạng hoặc thiếu tham số bắt buộc.'), 400


@app.errorhandler(403)
def handle_error_403(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Từ chối truy cập (Forbidden)'}), 403
    return render_template('error.html', code=403, title='Từ chối truy cập', message='Bạn không có quyền truy cập vào khu vực này hoặc yêu cầu bị chặn bởi cơ chế bảo vệ CSRF.'), 403


@app.errorhandler(404)
def handle_error_404(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Tài nguyên không tồn tại'}), 404
    return render_template('error.html', code=404, title='Không tìm thấy trang', message='Trang hoặc sản phẩm bạn đang tìm kiếm không tồn tại hoặc đã được gỡ bỏ.'), 404


@app.errorhandler(413)
def handle_error_413(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Dữ liệu tải lên vượt quá giới hạn cho phép (tối đa 16MB)'}), 413
    return render_template('error.html', code=413, title='Tệp quá lớn', message='Dung lượng tệp tải lên vượt quá giới hạn an toàn tối đa cho phép của máy chủ (tối đa 16MB).'), 413


@app.errorhandler(429)
def handle_error_429(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Quá nhiều yêu cầu. Vui lòng thử lại sau.'}), 429
    return render_template('error.html', code=429, title='Quá nhiều yêu cầu', message='Hệ thống phát hiện tần suất gửi yêu cầu quá nhanh. Vui lòng chờ giây lát rồi thao tác tiếp.'), 429


@app.errorhandler(500)
def handle_error_500(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Lỗi máy chủ nội bộ'}), 500
    return render_template('error.html', code=500, title='Sự cố hệ thống', message='Đã xảy ra sự cố nội bộ. Đội ngũ kỹ thuật đã được thông báo để khắc phục sớm nhất.'), 500


# ============================================
#   TẠO DATABASE + TÀI KHOẢN ADMIN MẶC ĐỊNH
# ============================================

def create_default_admin():
    """Tạo sẵn 1 tài khoản admin nếu chưa có, để bạn login lần đầu."""
    if not Admin.query.filter_by(username='admin').first():
        admin = Admin(username='admin')
        admin.set_password('admin123')  # NHỚ đổi mật khẩu này sau khi login lần đầu
        db.session.add(admin)
        db.session.commit()
        print(">>> Đã tạo tài khoản admin mặc định: username=admin, password=admin123")


with app.app_context():
    db.create_all()          # tạo các bảng nếu chưa có
    create_default_admin()   # tạo tài khoản admin mặc định


if __name__ == '__main__':
    app.run(debug=True)
