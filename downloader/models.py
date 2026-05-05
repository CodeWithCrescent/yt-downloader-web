import secrets

from django.db import models
from django.contrib.auth.models import User


class ShareLink(models.Model):
    """One row per share action; URL carries ?s=<token> for visit attribution."""

    CHANNEL_WHATSAPP = "whatsapp"
    CHANNEL_TWITTER = "twitter"
    CHANNEL_FACEBOOK = "facebook"
    CHANNEL_EMAIL = "email"
    CHANNEL_SMS = "sms"
    CHANNEL_TELEGRAM = "telegram"
    CHANNEL_LINKEDIN = "linkedin"
    CHANNEL_REDDIT = "reddit"
    CHANNEL_COPY = "copy"
    CHANNEL_NATIVE = "native"

    CHANNEL_CHOICES = [
        (CHANNEL_WHATSAPP, "WhatsApp"),
        (CHANNEL_TWITTER, "X (Twitter)"),
        (CHANNEL_FACEBOOK, "Facebook"),
        (CHANNEL_EMAIL, "Email"),
        (CHANNEL_SMS, "SMS / Messages"),
        (CHANNEL_TELEGRAM, "Telegram"),
        (CHANNEL_LINKEDIN, "LinkedIn"),
        (CHANNEL_REDDIT, "Reddit"),
        (CHANNEL_COPY, "Copy link"),
        (CHANNEL_NATIVE, "Web Share"),
    ]

    token = models.CharField(max_length=32, unique=True, db_index=True)
    channel = models.CharField(max_length=32, choices=CHANNEL_CHOICES, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    first_visited_at = models.DateTimeField(null=True, blank=True, db_index=True)
    visit_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.channel} {self.token[:8]}…"

    @staticmethod
    def new_token() -> str:
        return secrets.token_urlsafe(18)


class SiteVisit(models.Model):
    """One row per counted visit (deduped once per session per calendar day per path)."""

    visited_at = models.DateTimeField(auto_now_add=True, db_index=True)
    path = models.CharField(max_length=255, db_index=True)
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, blank=True)
    referrer = models.URLField(max_length=500, blank=True)
    share_link = models.ForeignKey(
        ShareLink,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="site_visits",
    )

    class Meta:
        ordering = ["-visited_at"]

    def __str__(self):
        return f"{self.path} @ {self.visited_at}"

class MediaDownload(models.Model):
    PLATFORM_CHOICES = [
        ('youtube', 'YouTube'),
        ('instagram', 'Instagram'),
        ('facebook', 'Facebook'),
        ('tiktok', 'TikTok'),
        ('pinterest', 'Pinterest'),
        ('twitter', 'Twitter/X'),
        ('reddit', 'Reddit'),
        ('vimeo', 'Vimeo'),
        ('dailymotion', 'Dailymotion'),
        ('twitch', 'Twitch'),
        ('other', 'Other'),
    ]
    
    MEDIA_TYPE_CHOICES = [
        ('video', 'Video'),
        ('image', 'Image'),
        ('audio', 'Audio'),
        ('post', 'Post'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    media_url = models.URLField(max_length=500)
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE_CHOICES)
    title = models.CharField(max_length=500, blank=True)
    thumbnail = models.URLField(blank=True)
    duration = models.CharField(max_length=20, blank=True)
    uploader = models.CharField(max_length=200, blank=True)
    file_size = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Admin tracking fields
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    referrer = models.URLField(max_length=500, blank=True, null=True)

    # One-time / time-limited file delivery (not the integer PK in URLs)
    delivery_token = models.UUIDField(
        null=True, blank=True, unique=True, db_index=True, editable=False
    )
    temp_file_path = models.CharField(max_length=1024, blank=True, default='')
    delivery_filename = models.CharField(max_length=255, blank=True, default='')
    file_ready_at = models.DateTimeField(null=True, blank=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title or self.media_url} - {self.platform} - {self.status}"

class MediaFormat(models.Model):
    download_instance = models.ForeignKey(MediaDownload, on_delete=models.CASCADE, related_name='formats')
    resolution = models.CharField(max_length=20)
    format_id = models.CharField(max_length=50)
    filesize = models.CharField(max_length=50, blank=True)
    extension = models.CharField(max_length=10)
    media_type = models.CharField(max_length=10, choices=MediaDownload.MEDIA_TYPE_CHOICES, default='video')
    
    class Meta:
        ordering = ['-resolution']
    
    def __str__(self):
        return f"{self.resolution} - {self.download_instance.title}"
    