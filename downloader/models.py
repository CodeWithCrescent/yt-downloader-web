from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class VideoDownload(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    video_url = models.URLField(max_length=500)
    video_title = models.CharField(max_length=500, blank=True)
    video_thumbnail = models.URLField(blank=True)
    video_duration = models.CharField(max_length=20, blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    file_size = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.video_title or self.video_url} - {self.status}"

class VideoFormat(models.Model):
    download_instance = models.ForeignKey(VideoDownload, on_delete=models.CASCADE, related_name='formats')
    resolution = models.CharField(max_length=20)
    format_id = models.CharField(max_length=50)
    filesize = models.CharField(max_length=50, blank=True)
    extension = models.CharField(max_length=10)
    download_url = models.URLField(blank=True)
    
    class Meta:
        ordering = ['-resolution']
    
    def __str__(self):
        return f"{self.resolution} - {self.download_instance.video_title}"
    