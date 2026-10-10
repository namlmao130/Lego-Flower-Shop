"""Extensions shared by models and routes, bound by create_app()."""

from flask_caching import Cache
from flask_compress import Compress
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
cache = Cache()
compress = Compress()
limiter = Limiter(get_remote_address)
login_manager = LoginManager()
login_manager.login_view = "admin_login"
