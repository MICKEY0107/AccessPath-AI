"""The bundled demo repository: AccessPath's own fixture site, ready without GitHub."""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.db import IntegrityError

from apps.journeys.models import ExecutionMode, Journey

from .models import RepoBinding, RepoSource
from .services import analyze_binding


def _origin(url: str) -> str:
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ""


def ensure_demo_binding(user) -> tuple[RepoBinding, int]:
    """Create (or refresh) the user's demo repository and link the fixture journeys.

    Only journeys with no repository (or already on this demo copy) are linked: a
    journey someone linked to another repository, theirs or anyone else's, is left alone.
    """
    site = settings.FIXTURE_ALLOWED_ORIGINS[0].rstrip("/")
    try:
        binding, _created = RepoBinding.objects.get_or_create(
            owner=user,
            source=RepoSource.BUNDLED,
            defaults={"repo_url": settings.DEMO_REPOSITORY_URL, "live_site_url": f"{site}/"},
        )
    except IntegrityError:  # A second click raced the first; use the copy it made.
        binding = RepoBinding.objects.get(owner=user, source=RepoSource.BUNDLED)
    analyze_binding(binding)
    linked = 0
    fixture_origins = {origin.rstrip("/") for origin in settings.FIXTURE_ALLOWED_ORIGINS}
    for journey in Journey.objects.filter(
        is_active=True, execution_mode=ExecutionMode.FIXTURE
    ).select_related("repo_binding"):
        if _origin(journey.start_url) not in fixture_origins:
            continue
        current = journey.repo_binding
        if current is not None and current.pk != binding.pk:
            continue
        if current is None:
            journey.repo_binding = binding
            journey.save(update_fields=["repo_binding", "updated_at"])
        linked += 1
    return binding, linked
