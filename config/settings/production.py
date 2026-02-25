"""
Django production settings.
Uses PostgreSQL, S3 storage, strict security.
"""

import os

from .base import *  # noqa: F401,F403

DEBUG = False

# ---------------------------------------------------------------------------
# Database — PostgreSQL
# ---------------------------------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "msie"),
        "USER": os.getenv("DB_USER", "msie"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "CONN_MAX_AGE": 600,
    }
}

# Support DATABASE_URL if provided (Railway/Render style)
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL:
    import dj_database_url
    DATABASES["default"] = dj_database_url.parse(DATABASE_URL, conn_max_age=600)

# ---------------------------------------------------------------------------
# Security
# ---------------------------------------------------------------------------

SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "true").lower() == "true"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# ---------------------------------------------------------------------------
# Static files — WhiteNoise
# ---------------------------------------------------------------------------

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"

# ---------------------------------------------------------------------------
# File storage — S3 (optional, fallback to local)
# ---------------------------------------------------------------------------

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
if AWS_ACCESS_KEY_ID:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
        },
    }
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "media-integrity-api")
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "us-east-1")
    AWS_S3_FILE_OVERWRITE = False
    AWS_DEFAULT_ACL = None

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
