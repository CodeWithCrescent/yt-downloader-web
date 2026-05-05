from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("downloader", "0009_mediadownload_delivery_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ShareLink",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("token", models.CharField(db_index=True, max_length=32, unique=True)),
                (
                    "channel",
                    models.CharField(
                        choices=[
                            ("whatsapp", "WhatsApp"),
                            ("twitter", "X (Twitter)"),
                            ("facebook", "Facebook"),
                            ("email", "Email"),
                            ("sms", "SMS / Messages"),
                            ("telegram", "Telegram"),
                            ("linkedin", "LinkedIn"),
                            ("reddit", "Reddit"),
                            ("copy", "Copy link"),
                            ("native", "Web Share"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "first_visited_at",
                    models.DateTimeField(blank=True, db_index=True, null=True),
                ),
                ("visit_count", models.PositiveIntegerField(default=0)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="SiteVisit",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("visited_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("path", models.CharField(db_index=True, max_length=255)),
                ("session_key", models.CharField(blank=True, db_index=True, max_length=40)),
                (
                    "ip_address",
                    models.GenericIPAddressField(blank=True, null=True),
                ),
                ("user_agent", models.CharField(blank=True, max_length=512)),
                ("referrer", models.URLField(blank=True, max_length=500)),
                (
                    "share_link",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="site_visits",
                        to="downloader.sharelink",
                    ),
                ),
            ],
            options={
                "ordering": ["-visited_at"],
            },
        ),
    ]
