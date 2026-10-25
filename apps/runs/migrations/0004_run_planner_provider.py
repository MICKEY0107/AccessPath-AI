from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("runs", "0003_run_planner_metadata")]

    operations = [
        migrations.AddField(
            model_name="run",
            name="planner_model",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="run",
            name="planner_provider",
            field=models.CharField(
                choices=[
                    ("gemini", "Gemini"),
                    ("openrouter", "OpenRouter"),
                    ("fixture", "Deterministic fixture"),
                ],
                default="gemini",
                max_length=16,
            ),
        ),
    ]
