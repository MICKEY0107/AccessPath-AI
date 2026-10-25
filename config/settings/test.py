"""Fast, hermetic test settings without external infrastructure."""

import os

# Test settings must be importable without a developer .env file. Production and
# local Compose environments still require DJANGO_SECRET_KEY from configuration.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-for-production")

from .base import *  # noqa: F403

SECRET_KEY = "test-only-secret-key"  # noqa: F405
DEBUG = False
ALLOWED_HOSTS = ["testserver"]
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
