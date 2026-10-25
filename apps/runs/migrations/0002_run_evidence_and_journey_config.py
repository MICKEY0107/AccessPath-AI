from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("journeys", "0001_initial"),
        ("runs", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="run",
            name="error_detail",
            field=models.TextField(blank=True),
        ),
        migrations.CreateModel(
            name="RunStep",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("step_number", models.PositiveIntegerField()),
                ("evidence", models.JSONField(default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="steps", to="runs.run")),
            ],
            options={"ordering": ["step_number"]},
        ),
        migrations.CreateModel(
            name="RunArtifact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=32)),
                ("relative_path", models.CharField(max_length=500)),
                ("sha256", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("run", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="artifacts", to="runs.run")),
                ("step", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="artifacts", to="runs.runstep")),
            ],
            options={"ordering": ["created_at"]},
        ),
        migrations.AddConstraint(
            model_name="runstep",
            constraint=models.UniqueConstraint(fields=("run", "step_number"), name="unique_run_step_number"),
        ),
    ]
