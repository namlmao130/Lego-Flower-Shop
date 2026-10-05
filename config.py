import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    # Mặc định dùng SQLite trong thư mục dự án, hoặc dùng DATABASE_URL nếu có cấu hình
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///' + os.path.join(BASE_DIR, 'shop.db'))
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Tối ưu SQLite cho nhiều request đồng thời:
    # - timeout: khi 1 request đang ghi (VD: đặt hàng, gửi review, chat) mà request khác cũng muốn ghi,
    #   SQLite sẽ CHỜ tối đa 15s thay vì báo lỗi "database is locked" ngay lập tức.
    # - pool_pre_ping: tự kiểm tra kết nối còn sống trước khi dùng, tránh lỗi kết nối "chết"
    #   khi server rảnh lâu rồi có traffic trở lại.
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'timeout': 15},
        'pool_pre_ping': True,
    }

    SECRET_KEY = os.environ.get('SECRET_KEY', 'doi-chuoi-nay-thanh-gi-do-bi-mat-cua-ban')

    # ------------------------------------------------------------------
    # CACHE + RATE LIMITING
    #
    # Mặc định (không cần làm gì thêm): lưu trong RAM -> chạy tốt với 1 worker,
    # đủ dùng cho đồ án / traffic nhỏ.
    #
    # Khi deploy thật với nhiều worker (Procfile hiện đặt --workers 4): mỗi worker
    # là 1 PROCESS RIÊNG, có vùng nhớ RAM RIÊNG. Hậu quả:
    #   - Cache category bị cache 4 LẦN khác nhau (tốn RAM, không nghiêm trọng)
    #   - Rate limit bị "pha loãng": "10 request/phút" thực tế thành ~40/phút
    #     (10 x 4 worker) vì mỗi worker tự đếm riêng, không biết worker khác đang đếm bao nhiêu
    #
    # Cách khắc phục: chạy Redis (1 chỗ lưu DÙNG CHUNG cho mọi worker) và set 1 biến
    # môi trường DUY NHẤT: REDIS_URL. VD:
    #   export REDIS_URL=redis://localhost:6379/0
    # Mọi cache/rate-limit sẽ TỰ ĐỘNG chuyển sang dùng Redis, không cần sửa code.
    # Không set REDIS_URL -> tự động dùng RAM như cũ, vẫn chạy bình thường.
    # ------------------------------------------------------------------
    REDIS_URL = os.environ.get('REDIS_URL', '').strip()
    _default_cache_type = 'RedisCache' if REDIS_URL else 'SimpleCache'
    _default_ratelimit_uri = REDIS_URL if REDIS_URL else 'memory://'

    CACHE_TYPE = os.environ.get('CACHE_TYPE', _default_cache_type)
    CACHE_REDIS_URL = os.environ.get('CACHE_REDIS_URL', REDIS_URL)
    CACHE_DEFAULT_TIMEOUT = 300
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', _default_ratelimit_uri)

    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    AVATAR_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads', 'avatars')
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ALLOWED_AVATAR_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'webm', 'mov', 'ogg'}
    ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS

    # Cấu hình gửi Email (ví dụ dùng Gmail SMTP hoặc dịch vụ khác)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'Lego Flower <noreply@legoflower.com>')
