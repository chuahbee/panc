from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0026_contactpage"),
    ]

    operations = [
        migrations.AddField(
            model_name="contactpage",
            name="working_days",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
