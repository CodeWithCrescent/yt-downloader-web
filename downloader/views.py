from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, FileResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.conf import settings
from .models import VideoDownload, VideoFormat
from .video_downloader import VideoDownloader
from .tasks import get_video_info_task, process_video_download
import json
import os

def home(request):
    """Home page with video URL input"""
    return render(request, 'downloader/home.html')

@csrf_exempt
@require_http_methods(["POST"])
def get_video_info(request):
    """Get video information and available formats"""
    video_url = request.POST.get('video_url')
    
    if not video_url:
        return JsonResponse({'error': 'Please provide a video URL'}, status=400)
    
    # Validate URL
    if not VideoDownloader.validate_url(video_url):
        return JsonResponse({'error': 'Invalid or unsupported video URL'}, status=400)
    
    # Start async task to get video info
    user_id = request.user.id if request.user.is_authenticated else None
    task = get_video_info_task.delay(video_url, user_id)
    
    return JsonResponse({
        'status': 'processing',
        'task_id': task.id,
        'message': 'Fetching video information...'
    })

@require_http_methods(["GET"])
def check_video_status(request, task_id):
    """Check status of video info fetching task"""
    from celery.result import AsyncResult
    task = AsyncResult(task_id)
    
    if task.ready():
        result = task.result
        if result['status'] == 'success':
            download_id = result['download_id']
            download_obj = VideoDownload.objects.get(id=download_id)
            formats = list(download_obj.formats.values('resolution', 'format_id', 'filesize', 'extension'))
            
            return JsonResponse({
                'status': 'ready',
                'download_id': download_id,
                'title': download_obj.video_title,
                'thumbnail': download_obj.video_thumbnail,
                'duration': download_obj.video_duration,
                'formats': formats
            })
        else:
            return JsonResponse({'status': 'error', 'error': result.get('error', 'Unknown error')})
    else:
        return JsonResponse({'status': 'loading'})

@csrf_exempt
@require_http_methods(["POST"])
def start_download(request):
    """Start the actual download process"""
    download_id = request.POST.get('download_id')
    format_id = request.POST.get('format_id')
    
    if not download_id or not format_id:
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    download_obj = get_object_or_404(VideoDownload, id=download_id)
    
    # Start async download task
    task = process_video_download.delay(download_id, format_id)
    
    return JsonResponse({
        'status': 'downloading',
        'task_id': task.id,
        'message': 'Download started...'
    })

@require_http_methods(["GET"])
def check_download_status(request, task_id):
    """Check download status"""
    from celery.result import AsyncResult
    task = AsyncResult(task_id)
    
    if task.ready():
        result = task.result
        if result['status'] == 'completed':
            return JsonResponse({
                'status': 'completed',
                'file_url': result['file_path']
            })
        else:
            return JsonResponse({
                'status': 'failed',
                'error': result.get('error', 'Download failed')
            })
    else:
        return JsonResponse({'status': 'downloading'})

@login_required
def my_downloads(request):
    """User's download history"""
    downloads = VideoDownload.objects.filter(user=request.user)
    paginator = Paginator(downloads, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'downloader/downloads.html', {'page_obj': page_obj})

@login_required
def download_file(request, download_id):
    """Serve the downloaded file"""
    download_obj = get_object_or_404(VideoDownload, id=download_id, user=request.user)
    
    if download_obj.status != 'completed' or not download_obj.file_path:
        return HttpResponse('File not available', status=404)
    
    file_path = download_obj.file_path.path
    
    if os.path.exists(file_path):
        response = FileResponse(open(file_path, 'rb'), content_type='video/mp4')
        response['Content-Disposition'] = f'attachment; filename="{download_obj.video_title}.mp4"'
        return response
    else:
        return HttpResponse('File not found', status=404)
        