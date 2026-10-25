from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("runs", "0002_run_evidence_and_journey_config")]

    operations = [
        migrations.AddField(
            model_name="run",
            name="planner_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
