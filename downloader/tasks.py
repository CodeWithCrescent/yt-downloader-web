from celery import shared_task
from django.utils import timezone
from .models import MediaDownload, MediaFormat
from .media_downloader import MediaDownloader
from django.core.cache import cache
import os
import tempfile
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True, max_retries=3)
def process_media_download(self, download_id, format_id):
    """Process media download and return download URL (without saving permanently)"""
    try:
        logger.info(f"Starting download process for ID: {download_id}")
        download_obj = MediaDownload.objects.get(id=download_id)
        download_obj.status = 'processing'
        download_obj.save()
        
        downloader = MediaDownloader()
        
        # Create temporary file for download
        with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
            temp_path = tmp_file.name
        
        # Download the media to temporary file
        file_path, file_size, error = downloader.download_media(
            download_obj.media_url,
            format_id,
            download_obj.title,
            download_obj.media_type,
            temp_path  # Pass temporary file path
        )

        # Store file info in cache for retrieval (expires after 1 hour)
        cache_key = f'download_file_{download_id}'
        cache.set(cache_key, {
            'file_path': file_path,
            'filename': f"{download_obj.title[:100]}.mp4",
            'file_size': file_size
        }, timeout=3600)  # 1 hour expiry
        
        if error:
            download_obj.status = 'failed'
            download_obj.save()
            logger.error(f"Download failed for ID {download_id}: {error}")
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return {'status': 'failed', 'error': error}
        
        # Update download record with file info (but don't save file permanently)
        download_obj.file_size = file_size
        download_obj.status = 'completed'
        download_obj.completed_at = timezone.now()
        download_obj.save()
        
        # Store temporary file path in task result (will be cleaned up after download)
        result = {
            'status': 'completed',
            'file_path': file_path,
            'file_size': file_size,
            'filename': f"{download_obj.title[:100]}.mp4",
            'download_id': download_id
        }
        
        logger.info(f"Download completed for ID {download_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in process_media_download for ID {download_id}: {str(e)}")
        try:
            download_obj = MediaDownload.objects.get(id=download_id)
            download_obj.status = 'failed'
            download_obj.save()
        except:
            pass
        
        # Clean up temp file if exists
        if 'temp_path' in locals() and os.path.exists(temp_path):
            os.remove(temp_path)
        
        # Retry the task if it's a temporary error
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        return {'status': 'failed', 'error': str(e)}


@shared_task(bind=True, max_retries=2)
def get_media_info_task(self, media_url, user_id=None):
    """Get media information asynchronously"""
    logger.info(f"Getting media info for URL: {media_url}")
    downloader = MediaDownloader()
    
    # Clean URL first
    clean_url = downloader.clean_url(media_url)
    
    # Validate URL
    if not downloader.validate_url(clean_url):
        return {'status': 'error', 'error': 'Unsupported URL or platform'}
    
    try:
        info, error = downloader.extract_media_info(clean_url)
        
        if error:
            logger.error(f"Error extracting info: {error}")
            return {'status': 'error', 'error': error}
        
        # Save to database
        from django.contrib.auth.models import User
        user = User.objects.get(id=user_id) if user_id else None
        
        # Ensure title is not too long
        title = info.get('title', 'Untitled')[:500]
        
        download_obj = MediaDownload.objects.create(
            user=user,
            media_url=clean_url,
            platform=info['platform'],
            media_type=info['media_type'],
            title=title,
            thumbnail=info.get('thumbnail', ''),
            duration=info.get('duration', ''),
            uploader=info.get('uploader', ''),
            status='pending',
            metadata={
                'caption': info.get('caption', ''),
                'like_count': info.get('like_count', 0),
                'comment_count': info.get('comment_count', 0),
                'has_multiple': info.get('has_multiple', False),
                'description': info.get('description', ''),
            }
        )
        
        # Save formats
        for fmt in info['formats']:
            MediaFormat.objects.create(
                download_instance=download_obj,
                resolution=fmt.get('resolution', 'Unknown'),
                format_id=str(fmt.get('format_id', 'best')),
                filesize=fmt.get('filesize', 'Unknown'),
                extension=fmt.get('extension', 'mp4'),
                media_type=fmt.get('type', info['media_type'])
            )
        
        logger.info(f"Media info saved with ID: {download_obj.id}")
        return {
            'status': 'success',
            'download_id': download_obj.id,
            'info': info
        }
        
    except Exception as e:
        logger.error(f"Error in get_media_info_task: {str(e)}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30)
        return {'status': 'error', 'error': str(e)}


@shared_task
def cleanup_temp_file(file_path):
    """Clean up temporary file after download"""
    try:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleaned up temp file: {file_path}")
    except Exception as e:
        logger.error(f"Error cleaning up temp file: {str(e)}")

