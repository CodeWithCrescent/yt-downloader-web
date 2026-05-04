from datetime import timezone

from celery import shared_task
from django.core.files import File
from django.core.files.base import ContentFile
from .models import VideoDownload, VideoFormat
from .video_downloader import VideoDownloader
import os
from django.conf import settings

@shared_task
def process_video_download(download_id, format_id):
    """Process video download asynchronously"""
    try:
        download_obj = VideoDownload.objects.get(id=download_id)
        download_obj.status = 'processing'
        download_obj.save()
        
        downloader = VideoDownloader()
        
        # Download the video
        file_path, file_size, error = downloader.download_video(
            download_obj.video_url,
            format_id,
            download_obj.video_title
        )
        
        if error:
            download_obj.status = 'failed'
            download_obj.save()
            return {'status': 'failed', 'error': error}
        
        # Save file to media directory
        with open(file_path, 'rb') as f:
            content = ContentFile(f.read())
            filename = os.path.basename(file_path)
            
            # Save to Django's media system
            download_obj.file_path.save(filename, content)
            download_obj.file_size = file_size
            download_obj.status = 'completed'
            download_obj.completed_at = timezone.now()
            download_obj.save()
        
        # Clean up temp file
        downloader.cleanup_temp_file(file_path)
        
        return {'status': 'completed', 'file_path': download_obj.file_path.url}
        
    except Exception as e:
        if 'download_obj' in locals():
            download_obj.status = 'failed'
            download_obj.save()
        return {'status': 'failed', 'error': str(e)}

@shared_task
def get_video_info_task(video_url, user_id=None):
    """Get video information asynchronously"""
    downloader = VideoDownloader()
    info, error = downloader.extract_video_info(video_url)
    
    if error:
        return {'status': 'error', 'error': error}
    
    # Save to database
    from django.contrib.auth.models import User
    user = User.objects.get(id=user_id) if user_id else None
    
    download_obj = VideoDownload.objects.create(
        user=user,
        video_url=video_url,
        video_title=info['title'],
        video_thumbnail=info['thumbnail'],
        video_duration=info['duration'],
        status='pending'
    )
    
    # Save formats
    for fmt in info['formats']:
        VideoFormat.objects.create(
            download_instance=download_obj,
            resolution=fmt['resolution'],
            format_id=fmt['format_id'],
            filesize=fmt['filesize'],
            extension=fmt['extension']
        )
    
    return {
        'status': 'success',
        'download_id': download_obj.id,
        'info': info
    }
