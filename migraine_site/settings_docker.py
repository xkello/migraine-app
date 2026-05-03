from pathlib import Path
import os

# ── Import all base settings first ───────────────────────────────────────────
# This also imports settings_local.py (SQLite, DEBUG=True).
# We override the relevant parts below.
from migraine_site.settings import *   # noqa: F401, F403

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Database — PostgreSQL driven by environment variables ────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME":     os.getenv("DB_NAME",     "migraine_db"),
        "USER":     os.getenv("DB_USER",     "migraine_user"),
        "PASSWORD": os.getenv("DB_PASSWORD", "migraine_local_pw"),
        "HOST":     os.getenv("DB_HOST",     "db"),
        "PORT":     os.getenv("DB_PORT",     "5432"),
    }
}

# ── Security ─────────────────────────────────────────────────────────────────
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "django-insecure-local-dev-key-change-in-production",
)

DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

# Accept the container hostname, localhost, and any extra hosts from env
_extra_hosts = [h for h in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if h]
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "0.0.0.0", "web"] + _extra_hosts

# ── Static files ──────────────────────────────────────────────────────────────
# Use plain StaticFilesStorage so collectstatic works without a manifest
# (ManifestStaticFilesStorage is the production default in settings.py).
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

# ── File-based cache ──────────────────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": BASE_DIR / "django_cache",
    }
}

# ── Weather API ───────────────────────────────────────────────────────────────
WEATHER_API_KEY  = os.getenv("WEATHER_API_KEY",  "9d4d68e8d2dcc76b2cfc8e1132b0975f")
OWM_API_BASE     = os.getenv("OWM_API_BASE",     "https://api.openweathermap.org")
OWM_HISTORY_BASE = os.getenv("OWM_HISTORY_BASE", "https://history.openweathermap.org")

# ── ML model storage ──────────────────────────────────────────────────────────
ML_MODELS_DIR = BASE_DIR / "models"

