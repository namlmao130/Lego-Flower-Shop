import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


def load_project_env(base_dir):
    """Nạp cấu hình cục bộ từ .env mà không ghi đè biến môi trường khi deploy."""
    env_path = os.path.join(base_dir, ".env")
    if not os.path.isfile(env_path):
        return

    try:
        with open(env_path, "r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                    value = value[1:-1]
                if key:
                    os.environ.setdefault(key, value)
    except OSError:
        # Không để lỗi file cấu hình cục bộ làm ứng dụng không khởi động được.
        pass


load_project_env("/etc/secrets")
load_project_env(BASE_DIR)


def normalize_database_url(value):
    for prefix in ("postgres://", "postgresql://"):
        if value.startswith(prefix):
            return "postgresql+psycopg://" + value[len(prefix) :]
    return value


def get_or_create_secret_key(base_dir):
    """Đảm bảo SECRET_KEY luôn là chuỗi ngẫu nhiên bảo mật cao, không dùng chuỗi mặc định dễ đoán."""
    env_secret = os.environ.get("SECRET_KEY", "").strip()
    if env_secret and env_secret != "doi-chuoi-nay-thanh-gi-do-bi-mat-cua-ban":
        return env_secret
    key_path = os.path.join(base_dir, ".secret_key")
    if os.path.isfile(key_path):
        try:
            with open(key_path, "r", encoding="utf-8") as f:
                k = f.read().strip()
                if k:
                    return k
        except Exception:
            pass
    import secrets

    new_key = secrets.token_hex(32)
    try:
        with open(key_path, "w", encoding="utf-8") as f:
            f.write(new_key)
    except Exception:
        pass
    return new_key


class Config:
    # Mặc định dùng SQLite trong thư mục dự án, hoặc dùng DATABASE_URL nếu có cấu hình
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL", "").strip() or (
        "sqlite:///" + os.path.join(BASE_DIR, "shop.db")
    )
    SQLALCHEMY_DATABASE_URI = normalize_database_url(SQLALCHEMY_DATABASE_URI)
    if os.environ.get(
        "REQUIRE_POSTGRES", ""
    ).lower() == "true" and not SQLALCHEMY_DATABASE_URI.startswith("postgresql"):
        raise RuntimeError("DATABASE_URL must point to PostgreSQL for this deployment.")

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Tối ưu SQLite cho nhiều request đồng thời:
    # - timeout: khi 1 request đang ghi (VD: đặt hàng, gửi review, chat) mà request khác cũng muốn ghi,
    #   SQLite sẽ CHỜ tối đa 15s thay vì báo lỗi "database is locked" ngay lập tức.
    # - pool_pre_ping: tự kiểm tra kết nối còn sống trước khi dùng, tránh lỗi kết nối "chết"
    #   khi server rảnh lâu rồi có traffic trở lại.
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    if SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        SQLALCHEMY_ENGINE_OPTIONS["connect_args"] = {"timeout": 15, "check_same_thread": False}
    elif SQLALCHEMY_DATABASE_URI.startswith("postgresql"):
        SQLALCHEMY_ENGINE_OPTIONS.update(
            connect_args={"connect_timeout": 10},
            pool_size=5,
            max_overflow=5,
        )

    SECRET_KEY = get_or_create_secret_key(BASE_DIR)

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
    REDIS_URL = os.environ.get("REDIS_URL", "").strip()
    _default_cache_type = "RedisCache" if REDIS_URL else "SimpleCache"
    _default_ratelimit_uri = REDIS_URL if REDIS_URL else "memory://"

    CACHE_TYPE = os.environ.get("CACHE_TYPE", _default_cache_type)
    CACHE_REDIS_URL = os.environ.get("CACHE_REDIS_URL", REDIS_URL)
    CACHE_DEFAULT_TIMEOUT = 300
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", _default_ratelimit_uri)
    RATELIMIT_DEFAULT = os.environ.get("RATELIMIT_DEFAULT", "1200 per minute, 20000 per hour")

    # Bảo mật Session và Cookie
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in (
        "true",
        "1",
    )
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = os.environ.get("SESSION_COOKIE_SECURE", "false").lower() in (
        "true",
        "1",
    )

    # Giới hạn kích thước payload tối đa (16MB) chống tấn công làm tràn bộ đệm máy chủ
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    AVATAR_UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads", "avatars")
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    ALLOWED_AVATAR_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
    ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "mov", "ogg"}
    ALLOWED_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_VIDEO_EXTENSIONS

    # Cấu hình gửi Email (ví dụ dùng Gmail SMTP hoặc dịch vụ khác)
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in ["true", "1"]
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    # Để trống sẽ tự dùng MAIL_USERNAME, tránh dùng địa chỉ "From" chưa được SMTP cho phép.
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "").strip()
