from django.contrib import admin
from .models import VideoDownload, VideoFormat

@admin.register(VideoDownload)
class VideoDownloadAdmin(admin.ModelAdmin):
    list_display = ['id', 'video_title', 'user', 'status', 'created_at']
    list_filter = ['status', 'created_at']
    search_fields = ['video_title', 'video_url']
    readonly_fields = ['created_at', 'completed_at']

@admin.register(VideoFormat)
class VideoFormatAdmin(admin.ModelAdmin):
    list_display = ['id', 'download_instance', 'resolution', 'filesize']
    list_filter = ['resolution']
    