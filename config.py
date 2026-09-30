import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _flag(name, default="false"):
    value = os.environ.get(name, default)
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "postgresql+psycopg://neuralxpert:neuralxpert@localhost:5432/neuralxpert",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SITE_URL = os.environ.get("SITE_URL", "https://neuralxpert.com")
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "instance/uploads")
    ALLOWED_CV_EXTENSIONS = {"pdf", "doc", "docx"}
    ARTICLES_PER_PAGE = 6
    WTF_CSRF_TIME_LIMIT = 60 * 60 * 8
    SESSION_COOKIE_NAME = "nx_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    REMEMBER_COOKIE_HTTPONLY = True
    # Per-process limits. Account lockout is stored in the database, so it still applies across Gunicorn workers.
    RATELIMIT_STORAGE_URI = "memory://"
    MAIL_DEBUG = False
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = _flag("MAIL_USE_TLS", "true")
    MAIL_USE_SSL = _flag("MAIL_USE_SSL", "false")
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "Neural Xpert")
    MAIL_DEFAULT_RECIPIENT = os.environ.get("MAIL_DEFAULT_RECIPIENT", "")
    CONTACT_RECIPIENT = os.environ.get("CONTACT_RECIPIENT") or os.environ.get(
        "MAIL_DEFAULT_RECIPIENT", "partnerships@neuralxpert.com"
    )


class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///" + os.path.join(os.path.dirname(__file__), "instance", "dev.db"),
    )


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SITE_URL = "https://neuralxpert.com"
    UPLOAD_FOLDER = "instance/test-uploads"
    MAIL_SERVER = ""
    MAIL_SUPPRESS_SEND = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
