"""Configuration-driven journey specifications.

The first fixture is seeded as data in Phase 1B; targets and completion rules do
not live in view logic or browser code.
"""

from __future__ import annotations

from django.core.validators import MinLengthValidator
from django.db import models


class ExecutionMode(models.TextChoices):
    FIXTURE = "fixture", "Fixture"
    PUBLIC_READ_ONLY = "public_read_only", "Public read-only"
    SANDBOX_TRANSACTIONAL = "sandbox_transactional", "Sandbox transactional"


class Journey(models.Model):
    name = models.CharField(max_length=120, unique=True)
    goal = models.TextField(validators=[MinLengthValidator(10)])
    start_url = models.URLField(max_length=500)
    execution_mode = models.CharField(
        max_length=32,
        choices=ExecutionMode.choices,
        default=ExecutionMode.FIXTURE,
    )
    allowed_origins = models.JSONField(default=list)
    completion_policy = models.JSONField(default=dict)
    evaluation_config = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name
