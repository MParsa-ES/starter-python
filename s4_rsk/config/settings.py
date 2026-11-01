from pathlib import Path
from zoneinfo import ZoneInfo

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
# GEN-12: Load configuration from environment variables
env = environ.Env(
    DEBUG=(bool, False),
    PORT=(int, 8084),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1", "s4-rsk"]),
)

env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))

DEBUG = env("DEBUG")
SECRET_KEY = env("SECRET_KEY", default="unsafe-dev-secret-key" if DEBUG else None)
if not DEBUG and (not SECRET_KEY or SECRET_KEY.startswith(("unsafe-", "django-insecure-"))):
    from django.core.exceptions import ImproperlyConfigured

    raise ImproperlyConfigured("Set a non-development SECRET_KEY when DEBUG=False.")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
SERVICE_NAME = env("SERVICE_NAME", default="s4-rsk")
# CORS: origins allowed to call this API from a browser (frontend dev server)
CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=["http://localhost:5173", "http://127.0.0.1:5173"],
)
CORS_EXPOSE_HEADERS = ["X-Correlation-ID"]

# Application definition
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party apps
    "rest_framework",
    "corsheaders",
    "drf_spectacular",
    # S4-RSK Local Apps
    "common",
    "rules",
    "assessments",
    "reviews",
]

MIDDLEWARE = [
    "common.middleware.CorrelationIdMiddleware",  # GEN-08: Must be first
    "corsheaders.middleware.CorsMiddleware",  # must be before CommonMiddleware
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# PostgreSQL Database Configuration (Isolated per Service)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="s4_rsk_db"),
        "USER": env("POSTGRES_USER", default="s4_rsk_user"),
        "PASSWORD": env("POSTGRES_PASSWORD", default="s4_rsk_password"),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env("POSTGRES_PORT", default="5434"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
    }
}

# GEN-05: Transport & Storage in UTC; "Day" boundary calculations in Asia/Tehran
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
BUSINESS_TIMEZONE = ZoneInfo("Asia/Tehran")

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Django REST Framework Settings
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "common.pagination.LabBankCursorPagination",
    "EXCEPTION_HANDLER": "common.exceptions.rfc9457_exception_handler",
}

# GEN-01: OpenAPI 3.1 Specification Settings
SPECTACULAR_SETTINGS = {
    "TITLE": "LabBank S4-RSK (Risk & Fraud Decisioning) API",
    "DESCRIPTION": "Real-time transaction risk evaluation, dynamic rule engine, blocklist, and manual review service.",
    "VERSION": "1.0.0",
    "OAS_VERSION": "3.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Neighboring Services Configuration
S3_PAY_BASE_URL = env("S3_PAY_BASE_URL", default="http://s3-pay:8083")
S3_PAY_WEBHOOK_TIMEOUT_SECONDS = env.int("S3_PAY_WEBHOOK_TIMEOUT_SECONDS", default=5)
S3_PAY_WEBHOOK_MAX_RETRIES = env.int("S3_PAY_WEBHOOK_MAX_RETRIES", default=3)
# GEN-11: Structured JSON Logging with correlation_id & service name
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "correlation_id": {
            "()": "common.middleware.CorrelationIdLogFilter",
        },
    },
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(asctime)s %(levelname)s %(service)s %(correlation_id)s %(name)s %(message)s",
            "rename_fields": {
                "asctime": "timestamp",
                "levelname": "level",
            },
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["correlation_id"],
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
