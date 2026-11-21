"""Regression checks for deployment settings and unauthenticated probes."""

from __future__ import annotations

import pytest
from django.test import Client


def test_health_probe_is_public_and_minimal() -> None:
    response = Client().get("/healthz/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_readiness_probe_reports_database_readiness() -> None:
    response = Client().get("/readyz/")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_production_settings_apply_secure_defaults(monkeypatch) -> None:
    monkeypatch.setenv("DJANGO_ALLOWED_HOSTS", "accesspath.example.invalid")
    monkeypatch.setenv("SECURE_HSTS_SECONDS", "31536000")
    from config.settings import production

    assert production.DEBUG is False
    assert production.SESSION_COOKIE_SECURE is True
    assert production.CSRF_COOKIE_SECURE is True
    assert production.ALLOW_PRIVATE_NETWORKS is False


def test_production_environment_example_lists_required_settings() -> None:
    from pathlib import Path

    text = (Path(__file__).parents[1] / ".env.example").read_text(encoding="utf-8")
    assert "SECURE_HSTS_SECONDS" in text
