from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("downloader", "0008_alter_mediadownload_user_agent_default"),
    ]

    operations = [
        migrations.AddField(
            model_name="mediadownload",
            name="delivery_token",
            field=models.UUIDField(blank=True, db_index=True, editable=False, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="mediadownload",
            name="delivery_filename",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="mediadownload",
            name="file_ready_at",
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="mediadownload",
            name="temp_file_path",
            field=models.CharField(blank=True, default="", max_length=1024),
        ),
    ]
