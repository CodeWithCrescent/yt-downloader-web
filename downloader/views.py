from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponse, FileResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.files.base import ContentFile
from django.core.files.temp import NamedTemporaryFile
from .models import MediaDownload, MediaFormat
from .media_downloader import MediaDownloader
from .tasks import get_media_info_task, process_media_download, cleanup_temp_file
import json
import os
import mimetypes
from celery.result import AsyncResult
import logging
from wsgiref.util import FileWrapper

logger = logging.getLogger(__name__)

def home(request):
    """Home page with media URL input"""
    return render(request, 'downloader/home.html')

@csrf_exempt
@require_http_methods(["POST"])
def get_media_info(request):
    """Get media information and available formats"""
    media_url = request.POST.get('media_url')
    
    if not media_url:
        return JsonResponse({'error': 'Please provide a media URL'}, status=400)
    
    # Validate URL
    downloader = MediaDownloader()
    if not downloader.validate_url(media_url):
        return JsonResponse({'error': 'Invalid or unsupported URL'}, status=400)
    
    # Start async task to get media info
    user_id = request.user.id if request.user.is_authenticated else None
    task = get_media_info_task.delay(media_url, user_id)
    
    return JsonResponse({
        'status': 'processing',
        'task_id': task.id,
        'message': 'Fetching media information...'
    })

@require_http_methods(["GET"])
def check_media_status(request, task_id):
    """Check status of media info fetching task"""
    try:
        if not task_id:
            return JsonResponse({'status': 'error', 'error': 'Invalid task ID'})
        
        task = AsyncResult(task_id)
        
        if task.status == 'PENDING':
            return JsonResponse({'status': 'loading'})
        elif task.status == 'FAILURE':
            error_msg = str(task.info) if task.info else 'Task failed'
            return JsonResponse({'status': 'error', 'error': error_msg})
        elif task.ready():
            result = task.result
            if result and result.get('status') == 'success':
                download_id = result['download_id']
                download_obj = MediaDownload.objects.get(id=download_id)
                formats = list(download_obj.formats.values('resolution', 'format_id', 'filesize', 'extension', 'media_type'))
                
                response_data = {
                    'status': 'ready',
                    'download_id': download_id,
                    'platform': download_obj.get_platform_display(),
                    'title': download_obj.title,
                    'thumbnail': download_obj.thumbnail,
                    'duration': download_obj.duration,
                    'uploader': download_obj.uploader,
                    'media_type': download_obj.media_type,
                    'formats': formats,
                    'metadata': download_obj.metadata
                }
                
                # Add platform-specific info
                if download_obj.platform == 'instagram':
                    response_data['caption'] = download_obj.metadata.get('caption', '')
                    response_data['like_count'] = download_obj.metadata.get('like_count', 0)
                    response_data['comment_count'] = download_obj.metadata.get('comment_count', 0)
                
                return JsonResponse(response_data)
            else:
                error_msg = result.get('error', 'Unknown error') if result else 'No result available'
                return JsonResponse({'status': 'error', 'error': error_msg})
        else:
            return JsonResponse({'status': 'loading'})
            
    except Exception as e:
        logger.error(f"Error in check_media_status: {str(e)}")
        return JsonResponse({'status': 'error', 'error': str(e)})

@csrf_exempt
@require_http_methods(["POST"])
def start_download(request):
    """Start the actual download process"""
    download_id = request.POST.get('download_id')
    format_id = request.POST.get('format_id')
    
    if not download_id or not format_id:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        download_obj = get_object_or_404(MediaDownload, id=download_id)
        
        # Start async download task
        task = process_media_download.delay(download_id, format_id)
        
        return JsonResponse({
            'status': 'downloading',
            'task_id': task.id,
            'message': 'Download started...',
            'media_type': download_obj.media_type
        })
    except Exception as e:
        logger.error(f"Error starting download: {str(e)}")
        return JsonResponse({'status': 'error', 'error': str(e)}, status=500)

@require_http_methods(["GET"])
def check_download_status(request, task_id):
    """Check download status and return download URL when ready"""
    try:
        if not task_id:
            return JsonResponse({'status': 'error', 'error': 'Invalid task ID'})
        
        task = AsyncResult(task_id)
        
        if task.status == 'PENDING':
            return JsonResponse({'status': 'downloading', 'progress': 10, 'message': 'Initializing...'})
        elif task.status == 'FAILURE':
            error_msg = str(task.info) if task.info else 'Download failed'
            return JsonResponse({'status': 'failed', 'error': error_msg})
        elif task.status == 'STARTED':
            return JsonResponse({'status': 'downloading', 'progress': 30, 'message': 'Downloading media...'})
        elif task.status == 'PROGRESS':
            return JsonResponse({'status': 'downloading', 'progress': 60, 'message': 'Processing...'})
        elif task.ready():
            result = task.result
            if result and result.get('status') == 'completed':
                # Return the download URL instead of file directly
                return JsonResponse({
                    'status': 'ready',
                    'download_url': f'/download-file/{result["download_id"]}/',
                    'filename': result.get('filename', 'video.mp4'),
                    'file_size': result.get('file_size', 'Unknown')
                })
            else:
                error_msg = result.get('error', 'Download failed') if result else 'Unknown error'
                return JsonResponse({'status': 'failed', 'error': error_msg})
        else:
            return JsonResponse({'status': 'downloading', 'progress': 50, 'message': 'Processing...'})
            
    except Exception as e:
        logger.error(f"Error in check_download_status: {str(e)}")
        return JsonResponse({'status': 'error', 'error': str(e)})

@require_http_methods(["GET"])
def download_completed_file(request, download_id):
    """Stream the downloaded file directly to user's browser"""
    try:
        # Get the task result from cache or database
        from celery.result import AsyncResult
        from django.core.cache import cache
        
        # Try to get the file path from cache
        cache_key = f'download_file_{download_id}'
        file_info = cache.get(cache_key)
        
        if not file_info:
            # If not in cache, check if it's a recent download
            download_obj = MediaDownload.objects.get(id=download_id)
            if download_obj.status != 'completed':
                return HttpResponse('Download not ready or not found', status=404)
            
            # Try to get from task result (this would need to be stored)
            return HttpResponse('Download expired. Please try again.', status=404)
        
        file_path = file_info.get('file_path')
        filename = file_info.get('filename', 'video.mp4')
        
        if not file_path or not os.path.exists(file_path):
            return HttpResponse('File not found', status=404)
        
        # Stream the file to user
        chunk_size = 8192
        response = StreamingHttpResponse(
            FileWrapper(open(file_path, 'rb'), chunk_size),
            content_type='video/mp4'
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response['Content-Length'] = os.path.getsize(file_path)
        
        # Schedule cleanup after response is sent
        from django.db import connection
        connection.close()
        
        # Clean up temp file after streaming
        def clean_up():
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up temp file: {file_path}")
                # Remove from cache
                cache.delete(cache_key)
            except Exception as e:
                logger.error(f"Error cleaning up: {str(e)}")
        
        # Use a delayed cleanup (will run after response)
        import threading
        threading.Timer(5.0, clean_up).start()
        
        return response
        
    except Exception as e:
        logger.error(f"Error streaming file: {str(e)}")
        return HttpResponse(f'Error: {str(e)}', status=500)

@login_required
def my_downloads(request):
    """User's download history"""
    downloads = MediaDownload.objects.filter(user=request.user)
    
    # Filter by platform if specified
    platform = request.GET.get('platform')
    if platform:
        downloads = downloads.filter(platform=platform)
    
    # Filter by media type if specified
    media_type = request.GET.get('media_type')
    if media_type:
        downloads = downloads.filter(media_type=media_type)
    
    paginator = Paginator(downloads, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get platforms for filter
    platforms = MediaDownload.PLATFORM_CHOICES
    
    return render(request, 'downloader/downloads.html', {
        'page_obj': page_obj,
        'platforms': platforms,
        'current_platform': platform,
        'current_media_type': media_type
    })

def supported_platforms(request):
    """Return list of supported platforms"""
    platforms = [
        {'name': 'YouTube', 'icon': 'fab fa-youtube', 'color': 'red'},
        {'name': 'Instagram', 'icon': 'fab fa-instagram', 'color': 'pink'},
        {'name': 'Facebook', 'icon': 'fab fa-facebook', 'color': 'blue'},
        {'name': 'TikTok', 'icon': 'fab fa-tiktok', 'color': 'black'},
        {'name': 'Pinterest', 'icon': 'fab fa-pinterest', 'color': 'red'},
        {'name': 'Twitter/X', 'icon': 'fab fa-twitter', 'color': 'blue'},
        {'name': 'Reddit', 'icon': 'fab fa-reddit', 'color': 'orange'},
        {'name': 'Vimeo', 'icon': 'fab fa-vimeo', 'color': 'blue'},
        {'name': 'Dailymotion', 'icon': 'fab fa-dailymotion', 'color': 'blue'},
        {'name': 'Twitch', 'icon': 'fab fa-twitch', 'color': 'purple'},
    ]
    return JsonResponse({'platforms': platforms})
