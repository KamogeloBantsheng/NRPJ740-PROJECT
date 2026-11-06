"""Django settings for NPRJ740 Maintenance Request & Work-Order Management System.
Configured for PostgreSQL 16, server-side sessions, and strict security headers.
"""

from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .env import get_env

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Security settings
INSECURE_DEV_SECRET_KEY = "insecure-dev-key-change-in-production"
SECRET_KEY = get_env("DJANGO_SECRET_KEY", INSECURE_DEV_SECRET_KEY)
DEBUG = get_env("DJANGO_DEBUG", "false", cast=bool)  # Debug output is opt-in (Section 5.7)

if not DEBUG and SECRET_KEY == INSECURE_DEV_SECRET_KEY:
    raise ImproperlyConfigured("Set DJANGO_SECRET_KEY, or DJANGO_DEBUG=true for local development.")

ALLOWED_HOSTS = [h.strip() for h in get_env("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]
if "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")

# Application definition (No Django Admin per project specification)
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.locations",
    "apps.accounts",
    "apps.audit",
    "apps.workflow",
    "rest_framework",
    "drf_spectacular",
]

AUTH_USER_MODEL = "accounts.User"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "config.middleware.ForcePasswordChangeMiddleware",
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
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Database Configuration (PostgreSQL 16)
# DB_USER and DB_PASSWORD default to app role for runtime, overridden by owner role for migrations
DB_USER = get_env("DB_USER", get_env("DB_APP_USER", "nrpj_app"))
DB_PASSWORD = get_env("DB_PASSWORD", get_env("DB_APP_PASSWORD", "change-me-app-secret"))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": get_env("DB_NAME", "nrpj740_dev"),
        "USER": DB_USER,
        "PASSWORD": DB_PASSWORD,
        "HOST": get_env("DB_HOST", "127.0.0.1"),
        "PORT": get_env("DB_PORT", "5432"),
        "OPTIONS": {
            # Section 5.7: stops one runaway query holding a connection. 0 turns it off for migrations.
            "options": f"-c statement_timeout={get_env('DB_STATEMENT_TIMEOUT_MS', 30000, cast=int)}",
        },
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-za"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Default primary key field type (64-bit BigAutoField per Table 5.7)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Session & Cookie Security (ADR-03 / NFR-02)
SESSION_ENGINE = "django.contrib.sessions.backends.db"
SESSION_COOKIE_AGE = get_env("SESSION_COOKIE_AGE", 28800, cast=int)  # 8 hours
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG

CSRF_COOKIE_HTTPONLY = False  # Frontend needs to read CSRF token to include in header
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = not DEBUG
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in get_env(
        "CSRF_TRUSTED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080",
    ).split(",")
    if origin.strip()
]

# Reverse proxies in front of Django that append to X-Forwarded-For. 0 means ignore that header.
TRUSTED_PROXY_COUNT = get_env("TRUSTED_PROXY_COUNT", 0, cast=int)

# Django REST Framework configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "config.exceptions.standard_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "NRPJ740 Campus Maintenance Request & Work-Order Management API",
    "DESCRIPTION": (
        "OpenAPI 3.0 specification for Moroka Hall Residence Maintenance System "
        "at Sol Plaatje University (NFR-09, Section 6.3)"
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Pinned: the "latest" ReDoc bundle fails to load, and a CDN update must not change the docs
    "SWAGGER_UI_DIST": "https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14",
    "REDOC_DIST": "https://cdn.jsdelivr.net/npm/redoc@2.1.5",
    "COMPONENT_SPLIT_REQUEST": True,
}

# Demo Data Seeding Settings (System Specification Section 4.8)
SEED_DEMO_DATA = get_env("SEED_DEMO_DATA", "false", cast=bool)
DEMO_PASSWORD = get_env("DEMO_PASSWORD", "DemoPass#2026")
