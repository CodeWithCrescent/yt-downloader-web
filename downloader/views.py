import json

from django.db import IntegrityError
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.text import slugify
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from .models import MediaDownload, MediaFormat, ShareLink
from .media_downloader import MediaDownloader
from .tasks import get_media_info_task, process_media_download
from .delivery import file_delivery_available
import os
import re
from uuid import UUID
from urllib.parse import quote
from celery.result import AsyncResult
import logging

logger = logging.getLogger(__name__)

VALID_SHARE_CHANNELS = frozenset(dict(ShareLink.CHANNEL_CHOICES).keys())


def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    return ip


@ensure_csrf_cookie
def home(request):
    """Home page with media URL input - SEO optimized single page"""
    # Track referrer for analytics
    request.session['referrer'] = request.META.get('HTTP_REFERER', '')
    return render(request, 'downloader/home.html')


def terms_of_service(request):
    return render(request, "downloader/terms.html")


def privacy_policy(request):
    return render(request, "downloader/privacy.html")

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

    # Store client info in session for later use
    request.session['client_ip'] = get_client_ip(request)
    request.session['user_agent'] = request.META.get('HTTP_USER_AGENT', '')

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
    """Start the actual download process with client tracking"""
    download_id = request.POST.get('download_id')
    format_id = request.POST.get('format_id')

    if not download_id or not format_id:
        return JsonResponse({'error': 'Missing parameters'}, status=400)

    try:
        download_obj = get_object_or_404(MediaDownload, id=download_id)

        # Capture client info for admin tracking
        download_obj.ip_address = get_client_ip(request)
        download_obj.user_agent = (request.META.get('HTTP_USER_AGENT') or '')[:500]
        download_obj.referrer = request.session.get('referrer', request.META.get('HTTP_REFERER', ''))[:500]
        download_obj.save(update_fields=['ip_address', 'user_agent', 'referrer'])

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
    """Check download status and return redirect URL for auto-download page"""
    try:
        if not task_id:
            return JsonResponse({'status': 'error', 'error': 'Invalid task ID'})

        task = AsyncResult(task_id)

        if task.status == 'PENDING':
            return JsonResponse({'status': 'downloading', 'progress': 10, 'message': 'Initializing...'})
        elif task.status == 'FAILURE':
            error_msg = str(task.info) if task.info else 'Download failed'
            # Update download status to failed
            try:
                result = task.result
                if result and result.get('download_id'):
                    MediaDownload.objects.filter(id=result['download_id']).update(status='failed')
            except:
                pass
            return JsonResponse({'status': 'failed', 'error': error_msg})
        elif task.status == 'STARTED':
            return JsonResponse({'status': 'downloading', 'progress': 40, 'message': 'Downloading from source...'})
        elif task.status == 'PROGRESS':
            return JsonResponse({'status': 'downloading', 'progress': 70, 'message': 'Processing video...'})
        elif task.ready():
            result = task.result
            if result and result.get('status') == 'completed':
                token = result.get('delivery_token')
                md = MediaDownload.objects.filter(id=result.get('download_id')).first()
                if not token and md and md.delivery_token:
                    token = str(md.delivery_token)
                if not token:
                    return JsonResponse({'status': 'failed', 'error': 'Missing delivery token.'})
                slug = slugify((md.title if md else '') or 'video')[:120] or 'video'
                return JsonResponse({
                    'status': 'ready',
                    'redirect_url': f'/ready/{token}/{slug}/',
                    'filename': result.get('filename', 'video.mp4'),
                    'file_size': result.get('file_size', 'Unknown'),
                })
            else:
                error_msg = result.get('error', 'Download failed') if result else 'Unknown error'
                return JsonResponse({'status': 'failed', 'error': error_msg})
        else:
            return JsonResponse({'status': 'downloading', 'progress': 55, 'message': 'Processing...'})

    except Exception as e:
        logger.error(f"Error in check_download_status: {str(e)}")
        return JsonResponse({'status': 'error', 'error': str(e)})

@require_http_methods(["GET"])
def download_page(request, token, slug=None):
    """Landing page before user taps Download (UUID + optional SEO slug)."""
    try:
        uid = UUID(str(token))
    except ValueError:
        return render(request, 'downloader/download_error.html', {
            'error': 'This link is not valid.',
        })

    download_obj = MediaDownload.objects.filter(delivery_token=uid).first()
    if not download_obj:
        return render(request, 'downloader/download_error.html', {
            'error': 'This link is invalid or has expired.',
        })

    if not file_delivery_available(download_obj):
        return render(request, 'downloader/download_error.html', {
            'error': 'This file has expired or was removed. Start again from the home page.',
        })

    filename = download_obj.delivery_filename or 'download'

    ext = os.path.splitext(filename)[1].lower()
    content_types = {
        '.mp4': 'video/mp4',
        '.webm': 'video/webm',
        '.mkv': 'video/x-matroska',
        '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime',
        '.mp3': 'audio/mpeg',
        '.m4a': 'audio/mp4',
        '.wav': 'audio/wav',
        '.ogg': 'audio/ogg',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    content_type = content_types.get(ext, 'application/octet-stream')

    return render(request, 'downloader/download_page.html', {
        'delivery_token': uid,
        'filename': filename,
        'title': download_obj.title,
        'thumbnail': download_obj.thumbnail,
        'content_type': content_type,
    })


def _ascii_download_filename(name):
    """Safe filename for Content-Disposition (ASCII fallback + RFC5987)."""
    base = os.path.basename(name or 'download')
    safe = re.sub(r'[^A-Za-z0-9._\- ]+', '_', base).strip() or 'download'
    return safe


def _iter_file_chunks(file_path, chunk_size=65536):
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


@require_http_methods(["GET"])
def download_completed_file(request, token, slug=None):
    """Stream the packaged file. File is removed only after TTL by periodic cleanup (not here)."""
    try:
        uid = UUID(str(token))
    except ValueError:
        return HttpResponse('Invalid link', status=404)

    download_obj = MediaDownload.objects.filter(delivery_token=uid).first()
    if not download_obj or not file_delivery_available(download_obj):
        return HttpResponse(
            'This link has expired or the file is no longer available. Start again from the home page.',
            status=404,
            content_type='text/plain; charset=utf-8',
        )

    file_path = (download_obj.temp_file_path or '').strip()
    filename = download_obj.delivery_filename or 'download'

    if not file_path or not os.path.isfile(file_path):
        return HttpResponse('File not found', status=404)

    ext = os.path.splitext(filename)[1].lower()
    content_types = {
        '.mp4': 'video/mp4',
        '.webm': 'video/webm',
        '.mkv': 'video/x-matroska',
        '.avi': 'video/x-msvideo',
        '.mov': 'video/quicktime',
        '.mp3': 'audio/mpeg',
        '.m4a': 'audio/mp4',
        '.wav': 'audio/wav',
        '.ogg': 'audio/ogg',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.webp': 'image/webp',
    }
    content_type = content_types.get(ext, 'application/octet-stream')

    ascii_name = _ascii_download_filename(filename)
    response = StreamingHttpResponse(_iter_file_chunks(file_path), content_type=content_type)
    response['Content-Length'] = os.path.getsize(file_path)
    response['Content-Disposition'] = (
        f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(os.path.basename(filename))}'
    )
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def download_success(request):
    """Simple success page after download"""
    return render(request, 'downloader/download_success.html')

@require_http_methods(["POST"])
def register_share(request):
    """Create a tracked share URL (?s=token) and return it for the chosen channel."""
    try:
        payload = json.loads(request.body.decode() or "{}")
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)
    channel = (payload.get("channel") or "").strip()
    if channel not in VALID_SHARE_CHANNELS:
        return JsonResponse({"error": "Unknown channel"}, status=400)

    obj = None
    for _ in range(8):
        token = ShareLink.new_token()
        try:
            obj = ShareLink.objects.create(token=token, channel=channel)
            break
        except IntegrityError:
            continue
    if not obj:
        return JsonResponse({"error": "Could not allocate token"}, status=500)

    root = request.build_absolute_uri("/").rstrip("/")
    share_url = f"{root}/?s={obj.token}"

    return JsonResponse(
        {
            "share_url": share_url,
            "token": obj.token,
            "channel": channel,
        }
    )


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
