# Generated manually from the Phase 1A model contract.

from django.core.validators import MinLengthValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Journey",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120, unique=True)),
                ("goal", models.TextField(validators=[MinLengthValidator(10)])),
                ("start_url", models.URLField(max_length=500)),
                (
                    "execution_mode",
                    models.CharField(
                        choices=[
                            ("fixture", "Fixture"),
                            ("public_read_only", "Public read-only"),
                            ("sandbox_transactional", "Sandbox transactional"),
                        ],
                        default="fixture",
                        max_length=32,
                    ),
                ),
                ("allowed_origins", models.JSONField(default=list)),
                ("completion_policy", models.JSONField(default=dict)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["name"]},
        ),
    ]
