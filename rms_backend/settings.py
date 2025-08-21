import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-not-for-prod")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

INSTALLED_APPS = [
    # Django
    "django.contrib.admin", "django.contrib.auth", "django.contrib.contenttypes",
    "django.contrib.sessions", "django.contrib.messages", "django.contrib.staticfiles",
    # 3rd party
    "rest_framework", "django_filters", "drf_spectacular", "corsheaders",
    # Apps
    "accounts", "core", "inventory", "menu", "orders", "reservations", "reports",
    "billing", "payments", "promotions", "storefront",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "rms_backend.urls"
WSGI_APPLICATION = "rms_backend.wsgi.application"
ASGI_APPLICATION = "rms_backend.asgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {
        "context_processors": [
            "django.template.context_processors.debug",
            "django.template.context_processors.request",
            "django.contrib.auth.context_processors.auth",
            "django.contrib.messages.context_processors.messages",
            "storefront.context.site_context",
        ],
    },
}]

# DB: SQLite for dev; use DATABASE_URL for Postgres in prod
if os.getenv("DATABASE_URL"):
    import urllib.parse as urlparse
    urlparse.uses_netloc.append("postgres")
    url = urlparse.urlparse(os.environ["DATABASE_URL"])
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": url.path[1:], "USER": url.username, "PASSWORD": url.password,
        "HOST": url.hostname, "PORT": url.port or "",
    }}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

# DRF + JWT hybrid
REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}
SPECTACULAR_SETTINGS = {
    "TITLE": "RMS API",
    "DESCRIPTION": "Restaurant/E-commerce API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# Static/media
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
WHITENOISE_USE_FINDERS = True
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# CORS (lock down in prod)
CORS_ALLOW_ALL_ORIGINS = True

# Storefront context
SITE_NAME = os.getenv("SITE_NAME", "RMS Store")
GA_MEASUREMENT_ID = os.getenv("GA_MEASUREMENT_ID", "")
WHATSAPP_NUMBER = os.getenv("WHATSAPP_NUMBER", "")
BRANCHES = [
    {
        "name": os.getenv("BRANCH1_NAME", "Head Office"),
        "address": os.getenv("BRANCH1_ADDR", "Putalisadak, Kathmandu"),
        "maps_iframe": os.getenv("BRANCH1_MAP", "https://www.google.com/maps?q=Kathmandu&output=embed"),
    },
    {
        "name": os.getenv("BRANCH2_NAME", "Branch 2"),
        "address": os.getenv("BRANCH2_ADDR", "Lalitpur, Nepal"),
        "maps_iframe": os.getenv("BRANCH2_MAP", "https://www.google.com/maps?q=Lalitpur&output=embed"),
    },
]
DEFAULT_CURRENCY = os.getenv("DEFAULT_CURRENCY", "NPR")
