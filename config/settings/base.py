"""Shared settings with environment-only configuration."""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("DJANGO_SECRET_KEY must be set outside the test environment.")

DEBUG = False
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",")
    if host.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.core",
    "apps.journeys",
    "apps.runs",
]

MIDDLEWARE = [
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
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.media",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

POSTGRES_DB = os.environ.get("POSTGRES_DB", "accesspath")
POSTGRES_USER = os.environ.get("POSTGRES_USER", "accesspath")
POSTGRES_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "")
POSTGRES_HOST = os.environ.get("POSTGRES_HOST", "127.0.0.1")
POSTGRES_PORT = os.environ.get("POSTGRES_PORT", "5432")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": POSTGRES_DB,
        "USER": POSTGRES_USER,
        "PASSWORD": POSTGRES_PASSWORD,
        "HOST": POSTGRES_HOST,
        "PORT": POSTGRES_PORT,
        "CONN_MAX_AGE": 60,
    }
}

AUTH_PASSWORD_VALIDATORS: list[dict[str, str]] = []
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/evidence/"
MEDIA_ROOT = BASE_DIR / "output"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

CELERY_BROKER_URL = os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300
CELERY_TASK_SOFT_TIME_LIMIT = 270

FIXTURE_ALLOWED_ORIGINS = tuple(
    origin.strip()
    for origin in os.environ.get("FIXTURE_ALLOWED_ORIGINS", "http://127.0.0.1:8001").split(",")
    if origin.strip()
)
ALLOW_PRIVATE_NETWORKS = os.environ.get("ALLOW_PRIVATE_NETWORKS", "false").lower() == "true"
EVALUATOR_MAX_STEPS = int(os.environ.get("EVALUATOR_MAX_STEPS", "56"))
EVALUATOR_ACTION_TIMEOUT_MS = int(os.environ.get("EVALUATOR_ACTION_TIMEOUT_MS", "5000"))
EVALUATOR_HEADLESS = os.environ.get("EVALUATOR_HEADLESS", "true").lower() == "true"
EVALUATOR_BROWSER_EXECUTABLE = os.environ.get("EVALUATOR_BROWSER_EXECUTABLE", "") or None

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "")
PLANNER_MAX_CALLS_PER_RUN = int(os.environ.get("PLANNER_MAX_CALLS_PER_RUN", "40"))
PLANNER_CALL_TIMEOUT_SECONDS = float(os.environ.get("PLANNER_CALL_TIMEOUT_SECONDS", "30"))
PLANNER_MIN_CALL_INTERVAL_SECONDS = float(
    os.environ.get("PLANNER_MIN_CALL_INTERVAL_SECONDS", "15")
)
PLANNER_MAX_429_RETRIES = int(os.environ.get("PLANNER_MAX_429_RETRIES", "1"))
PLANNER_429_BACKOFF_SECONDS = float(os.environ.get("PLANNER_429_BACKOFF_SECONDS", "30"))
PLANNER_MAX_TRANSIENT_RETRIES = int(
    os.environ.get("PLANNER_MAX_TRANSIENT_RETRIES", "5")
)
PLANNER_TRANSIENT_BACKOFF_SECONDS = float(
    os.environ.get("PLANNER_TRANSIENT_BACKOFF_SECONDS", "15")
)
