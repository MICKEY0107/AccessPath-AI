"""A repository bound to a live site, cloned read-only and indexed for code mapping."""

from __future__ import annotations

from urllib.parse import urlparse

from django.conf import settings
from django.db import models


class RepoStatus(models.TextChoices):
    PENDING = "pending", "Waiting to clone"
    CLONING = "cloning", "Cloning and analysing"
    READY = "ready", "Ready"
    FAILED = "failed", "Failed"


class RepoSource(models.TextChoices):
    GIT = "git", "Git repository"
    BUNDLED = "bundled", "Bundled demo copy"


class RepoBinding(models.Model):
    """This repository + branch is the code behind this live site."""

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="repo_bindings"
    )
    repo_url = models.URLField(max_length=300)
    # "bundled" is the demo: a copy of AccessPath's own fixture site, never cloned.
    source = models.CharField(max_length=16, choices=RepoSource.choices, default=RepoSource.GIT)
    branch = models.CharField(max_length=100, blank=True)
    live_site_url = models.URLField(max_length=500, blank=True)
    status = models.CharField(max_length=16, choices=RepoStatus.choices, default=RepoStatus.PENDING)
    commit_sha = models.CharField(max_length=40, blank=True)
    error = models.TextField(blank=True)
    # Counts shown on the badge: files, components, controls, ids, test ids, patterns.
    summary = models.JSONField(default=dict, blank=True)
    analysed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner"],
                condition=models.Q(source="bundled"),
                name="one_demo_repository_per_owner",
            )
        ]

    def __str__(self) -> str:
        return f"{self.short_name} · {self.branch or 'default branch'}"

    @property
    def short_name(self) -> str:
        parsed = urlparse(self.repo_url)
        return f"{parsed.hostname or ''}{parsed.path.removesuffix('.git')}".lstrip("/")

    @property
    def is_bundled(self) -> bool:
        return self.source == RepoSource.BUNDLED

    @property
    def storage_dir(self):
        return settings.REPO_STORAGE_ROOT / str(self.pk)

    @property
    def source_dir(self):
        return self.storage_dir / "src"

    @property
    def index_path(self):
        return self.storage_dir / "index.json"

    def site_origin(self) -> str:
        parsed = urlparse(self.live_site_url)
        return f"{parsed.scheme}://{parsed.netloc}" if parsed.netloc else ""
