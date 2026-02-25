"""
Django development settings.
Uses SQLite, DEBUG=True, permissive CORS.
"""

from .base import *  # noqa: F401,F403

DEBUG = True

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# Allow all origins in development
CORS_ALLOW_ALL_ORIGINS = True

# Disable password validators in dev for convenience
AUTH_PASSWORD_VALIDATORS = []

# Console email backend for dev
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
