# Generated manually from the Phase 1A model contract.

import django.db.models.deletion
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [("journeys", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="Run",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("starting", "Starting"),
                            ("running", "Running"),
                            ("finalizing", "Finalizing"),
                            ("succeeded", "Succeeded"),
                            ("failed", "Failed"),
                            ("cancelled", "Cancelled"),
                        ],
                        default="queued",
                        max_length=16,
                    ),
                ),
                (
                    "outcome",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("completed", "Completed"),
                            ("blocked", "Blocked"),
                            ("inconclusive", "Inconclusive"),
                            ("environment_blocked", "Environment blocked"),
                            ("safety_stopped", "Safety stopped"),
                            ("agent_error", "Agent error"),
                            ("system_error", "System error"),
                        ],
                        default="pending",
                        max_length=24,
                    ),
                ),
                ("celery_task_id", models.CharField(blank=True, max_length=255)),
                ("terminal_reason", models.CharField(blank=True, max_length=128)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("finished_at", models.DateTimeField(blank=True, null=True)),
                (
                    "journey",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="runs", to="journeys.journey"),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="run",
            index=models.Index(fields=["journey", "-created_at"], name="run_journey_created_idx"),
        ),
    ]
