from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("journeys", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="journey",
            name="evaluation_config",
            field=models.JSONField(default=dict),
        ),
    ]
