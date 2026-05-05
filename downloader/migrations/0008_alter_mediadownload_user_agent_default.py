# Generated manually: ensure user_agent is never NULL on insert (Celery creates rows without request).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("downloader", "0007_alter_mediadownload_referrer"),
    ]

    operations = [
        migrations.AlterField(
            model_name="mediadownload",
            name="user_agent",
            field=models.TextField(blank=True, default=""),
        ),
    ]
