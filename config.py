import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


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
    WTF_CSRF_TIME_LIMIT = None
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    REMEMBER_COOKIE_HTTPONLY = True
    RATELIMIT_STORAGE_URI = "memory://"
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER", "partnerships@neuralxpert.com")
    CONTACT_RECIPIENT = os.environ.get("CONTACT_RECIPIENT", "partnerships@neuralxpert.com")


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
