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
    host.strip() for host in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()
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
    "apps.codebase",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Every page needs a signed-in user: the app stores repositories and saved API keys.
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "runs:list"
LOGOUT_REDIRECT_URL = "login"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
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
# Live journeys on real sites can need many paced model calls; the target policy
# caps a run at 15 minutes, so the worker limit sits just above that.
CELERY_TASK_TIME_LIMIT = int(os.environ.get("CELERY_TASK_TIME_LIMIT", "960"))
CELERY_TASK_SOFT_TIME_LIMIT = int(os.environ.get("CELERY_TASK_SOFT_TIME_LIMIT", "930"))

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
PLANNER_MIN_CALL_INTERVAL_SECONDS = float(os.environ.get("PLANNER_MIN_CALL_INTERVAL_SECONDS", "15"))
PLANNER_MAX_429_RETRIES = int(os.environ.get("PLANNER_MAX_429_RETRIES", "1"))
PLANNER_429_BACKOFF_SECONDS = float(os.environ.get("PLANNER_429_BACKOFF_SECONDS", "30"))
PLANNER_MAX_TRANSIENT_RETRIES = int(os.environ.get("PLANNER_MAX_TRANSIENT_RETRIES", "5"))
PLANNER_TRANSIENT_BACKOFF_SECONDS = float(os.environ.get("PLANNER_TRANSIENT_BACKOFF_SECONDS", "15"))
# Retries for a one-off bad answer (empty, truncated, or unroutable) before fallback.
PLANNER_MAX_INVALID_RETRIES = int(os.environ.get("PLANNER_MAX_INVALID_RETRIES", "3"))

# axe-core runs on each page a journey visits when this file exists. Install it with
# `python manage.py install_axe_core`; without it the report marks axe rules "not checked".
AXE_CORE_VERSION = os.environ.get("AXE_CORE_VERSION", "4.10.3")
AXE_CORE_PATH = Path(
    os.environ.get("AXE_CORE_PATH", str(BASE_DIR / "vendor" / "axe-core" / "axe.min.js"))
)
# Keyboard checks (focus visible, focus obscured, names, skip links, focus order) run
# during every evaluation unless turned off here.
EVALUATOR_RUN_CHECKS = os.environ.get("EVALUATOR_RUN_CHECKS", "true").lower() == "true"

# Local Ollama (no API key; code never leaves the machine). Set only from the server
# environment, never from a web form. From Docker, the host is host.docker.internal.
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "")
# Providers allowed to read private repository code in addition to the built-in rules
# (engine/code_safety.py), e.g. "openrouter" for a paid tier with a data agreement.
CODE_SAFE_PROVIDERS = tuple(
    item.strip() for item in os.environ.get("CODE_SAFE_PROVIDERS", "").split(",") if item.strip()
)

# Active codebase: read-only clones live outside the media folder so they are never served.
REPO_STORAGE_ROOT = Path(os.environ.get("REPO_STORAGE_ROOT", str(BASE_DIR / ".runtime" / "repos")))
REPO_ALLOWED_HOSTS = ("github.com", "gitlab.com", "bitbucket.org")
REPO_MAX_BYTES = int(os.environ.get("REPO_MAX_BYTES", str(200 * 1024 * 1024)))
REPO_MAX_FILES = int(os.environ.get("REPO_MAX_FILES", "20000"))
REPO_CLONE_TIMEOUT_SECONDS = int(os.environ.get("REPO_CLONE_TIMEOUT_SECONDS", "120"))
# Tests clone from local folders; production only clones https URLs from the hosts above.
REPO_ALLOW_FILE_URLS = False
# The demo repository is a copy of the bundled fixture site; this is the address shown
# for it (the project's own public repository, where the same files live).
# Where people open the app; used in links printed by commands such as demo_setup.
DEMO_SITE_URL = os.environ.get("DEMO_SITE_URL", "http://127.0.0.1:8000")
DEMO_REPOSITORY_URL = os.environ.get(
    "DEMO_REPOSITORY_URL", "https://github.com/MICKEY0107/AccessPath-AI"
)
# Use the run's AI provider to search the code when nothing exact is found, but only
# when that provider is allowed to read private code (engine/code_safety.py).
CODE_LOCATOR_USE_AI = os.environ.get("CODE_LOCATOR_USE_AI", "true").lower() == "true"
