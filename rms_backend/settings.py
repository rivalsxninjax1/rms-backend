# rms_backend/settings.py
import os
from pathlib import Path
from datetime import timedelta
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from project root (e.g., <repo>/.env)
load_dotenv(BASE_DIR / ".env")

# ---------------------------------------------------------------------
# Core Django
# ---------------------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-not-for-prod")
DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"

def _split_env_list(val, default=""):
    raw = os.getenv(val, default)
    return [x.strip() for x in raw.split(",") if x.strip()]

ALLOWED_HOSTS = _split_env_list("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost")
CSRF_TRUSTED_ORIGINS = _split_env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

AUTH_USER_MODEL = "accounts.User"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Timezone (feel free to change)
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Kathmandu")
USE_TZ = True
LANGUAGE_CODE = "en-us"
USE_I18N = True

# ---------------------------------------------------------------------
# Installed apps
# ---------------------------------------------------------------------
INSTALLED_APPS = [
    # Django
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # 3rd party
    "rest_framework",
    "django_filters",
    "drf_spectacular",
    "corsheaders",

    # Apps
    "accounts",
    "core",
    "inventory",
    "menu",
    "orders",
    "reservations",
    "reports",
    "billing",
    "payments",
    "promotions",
    "storefront",
]

# ---------------------------------------------------------------------
# Middleware (order matters)
#   - Session BEFORE CSRF
#   - CORS BEFORE Common
#   - WhiteNoise after Security
# ---------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "rms_backend.urls"
WSGI_APPLICATION = "rms_backend.wsgi.application"
ASGI_APPLICATION = "rms_backend.asgi.application"

# ---------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------
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

# ---------------------------------------------------------------------
# Database
#   - SQLite for dev
#   - DATABASE_URL for Postgres in prod
#     (supports postgres:// and postgresql://)
# ---------------------------------------------------------------------
if os.getenv("DATABASE_URL"):
    import urllib.parse as urlparse
    for scheme in ["postgres", "postgresql"]:
        if scheme not in urlparse.uses_netloc:
            urlparse.uses_netloc.append(scheme)
    url = urlparse.urlparse(os.environ["DATABASE_URL"])
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": url.path[1:],
            "USER": url.username,
            "PASSWORD": url.password,
            "HOST": url.hostname,
            "PORT": url.port or "",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# ---------------------------------------------------------------------
# DRF + JWT
# ---------------------------------------------------------------------
REST_FRAMEWORK = {

      "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    "DEFAULT_PARSER_CLASSES": (
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ),

    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny"
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend"
    ],
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

# ---------------------------------------------------------------------
# Static / Media
# ---------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
WHITENOISE_USE_FINDERS = True

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ---------------------------------------------------------------------
# CORS (tighten in production)
# ---------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = True
# If you need credentials/cookies:
# CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------
# Storefront context
# ---------------------------------------------------------------------
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

# ---------------------------------------------------------------------
# Stripe (test mode)
#   - Set these in .env:
#       STRIPE_PUBLIC_KEY=pk_test_xxx
#       STRIPE_SECRET_KEY=sk_test_xxx
#       STRIPE_WEBHOOK_SECRET=whsec_xxx
#       STRIPE_CURRENCY=npr
# ---------------------------------------------------------------------
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY", "")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_CURRENCY = os.getenv("STRIPE_CURRENCY", "npr")  # Stripe expects lowercase codes
