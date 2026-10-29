"""Persistent run lifecycle; execution details remain in the engine module."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class RunStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    STARTING = "starting", "Starting"
    RUNNING = "running", "Running"
    FINALIZING = "finalizing", "Finalizing"
    SUCCEEDED = "succeeded", "Succeeded"
    FAILED = "failed", "Failed"
    CANCELLED = "cancelled", "Cancelled"


class JourneyOutcome(models.TextChoices):
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    BLOCKED = "blocked", "Blocked"
    INCONCLUSIVE = "inconclusive", "Inconclusive"
    ENVIRONMENT_BLOCKED = "environment_blocked", "Environment blocked"
    SAFETY_STOPPED = "safety_stopped", "Safety stopped"
    AGENT_ERROR = "agent_error", "Agent error"
    SYSTEM_ERROR = "system_error", "System error"


class PlannerProvider(models.TextChoices):
    GEMINI = "gemini", "Gemini"
    OPENROUTER = "openrouter", "OpenRouter"
    GROQ = "groq", "Groq"
    OLLAMA = "ollama", "Ollama (local)"
    FIXTURE = "fixture", "Deterministic fixture"


class Run(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    journey = models.ForeignKey("journeys.Journey", on_delete=models.PROTECT, related_name="runs")
    status = models.CharField(max_length=16, choices=RunStatus.choices, default=RunStatus.QUEUED)
    outcome = models.CharField(
        max_length=24,
        choices=JourneyOutcome.choices,
        default=JourneyOutcome.PENDING,
    )
    celery_task_id = models.CharField(max_length=255, blank=True)
    planner_provider = models.CharField(
        max_length=16,
        choices=PlannerProvider.choices,
        default=PlannerProvider.GEMINI,
    )
    planner_model = models.CharField(max_length=255, blank=True)
    planner_metadata = models.JSONField(default=dict, blank=True)
    terminal_reason = models.CharField(max_length=128, blank=True)
    error_detail = models.TextField(blank=True)
    # site_barrier, agent_failure, provider_failure, environment, or "" when completed.
    failure_kind = models.CharField(max_length=24, blank=True)
    # Why a failed run was not blamed on the site, in plain words.
    diagnosis = models.TextField(blank=True)
    # One engine.contracts.RuleResultV1 per rule the run applied.
    rule_results = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["journey", "-created_at"], name="run_journey_created_idx")]

    def __str__(self) -> str:
        return f"{self.journey.name} — {self.id}"


class RunStep(models.Model):
    """Append-only browser evidence for a single evaluated keyboard action."""

    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="steps")
    step_number = models.PositiveIntegerField()
    evidence = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["step_number"]
        constraints = [
            models.UniqueConstraint(fields=["run", "step_number"], name="unique_run_step_number"),
        ]


class RunArtifact(models.Model):
    """Metadata for locally stored evidence; a storage adapter can replace this later."""

    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="artifacts")
    step = models.ForeignKey(
        RunStep,
        on_delete=models.SET_NULL,
        related_name="artifacts",
        null=True,
        blank=True,
    )
    kind = models.CharField(max_length=32)
    relative_path = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class FindingSeverity(models.TextChoices):
    CRITICAL = "critical", "Critical"
    SERIOUS = "serious", "Serious"
    MODERATE = "moderate", "Moderate"
    MINOR = "minor", "Minor"


class Finding(models.Model):
    """One accessibility problem a run found, tied to a catalog rule and its evidence."""

    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name="findings")
    finding_id = models.CharField(max_length=64)
    rule_id = models.CharField(max_length=96)
    wcag_criterion = models.CharField(max_length=16, blank=True)
    severity = models.CharField(max_length=16, choices=FindingSeverity.choices)
    status = models.CharField(max_length=16)
    source = models.CharField(max_length=16, default="accesspath")
    title = models.CharField(max_length=200)
    summary = models.TextField()
    step_number = models.PositiveIntegerField(null=True, blank=True)
    url = models.CharField(max_length=1000)
    ignored = models.BooleanField(default=False)
    # The full engine.contracts.FindingV1, including element details and confirmation.
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["run", "finding_id"], name="unique_run_finding"),
        ]

    def __str__(self) -> str:
        return f"{self.rule_id} — {self.title}"


class SavedCredential(models.Model):
    """A person's model settings for one provider; the key is stored only if they ask.

    ``encrypted_key`` is Fernet ciphertext keyed from SECRET_KEY with its own context,
    so it is useless without the server's secret and is never shown again.
    """

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="saved_credentials"
    )
    provider = models.CharField(max_length=16, choices=PlannerProvider.choices)
    encrypted_key = models.TextField(blank=True)
    key_hint = models.CharField(max_length=16, blank=True)
    default_model = models.CharField(max_length=255, blank=True)
    is_preferred = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "provider"], name="unique_owner_provider"),
        ]

    def __str__(self) -> str:
        return f"{self.owner} — {self.provider}"
