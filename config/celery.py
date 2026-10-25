"""Celery application configuration.

The worker is a separate process. Django web requests only create durable run
records; browser execution will be introduced through worker tasks.
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("accesspath")  # type: ignore[reportCallIssue]
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()
