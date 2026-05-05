import os
import re
import uuid
import logging

from celery import shared_task
from django.utils import timezone

from .models import MediaDownload, MediaFormat
from .media_downloader import MediaDownloader
from .delivery import run_purge_expired_deliveries

logger = logging.getLogger(__name__)


def _fit(value, max_len, default=""):
    s = (value or default or "")
    if not isinstance(s, str):
        s = str(s)
    return s[:max_len]


@shared_task
def purge_expired_delivery_files():
    return run_purge_expired_deliveries()


@shared_task(bind=True, max_retries=3)
def process_media_download(self, download_id, format_id):
    try:
        logger.info("Starting download process for ID: %s", download_id)
        download_obj = MediaDownload.objects.get(id=download_id)

        # Remove any previous packaged file for this job (e.g. user changed format)
        if download_obj.temp_file_path:
            old = (download_obj.temp_file_path or "").strip()
            if old and os.path.isfile(old):
                try:
                    os.remove(old)
                except OSError:
                    pass
        MediaDownload.objects.filter(pk=download_obj.pk).update(
            temp_file_path="",
            delivery_filename="",
            delivery_token=None,
            file_ready_at=None,
        )
        download_obj.refresh_from_db()

        download_obj.status = "processing"
        download_obj.save()

        downloader = MediaDownloader()
        file_path, file_size, error = downloader.download_media(
            download_obj.media_url,
            format_id,
            download_obj.title,
            download_obj.media_type,
        )

        if error:
            download_obj.status = "failed"
            download_obj.save()
            logger.error("Download failed for ID %s: %s", download_id, error)
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
            return {"status": "failed", "error": error}

        if not file_path or not os.path.isfile(file_path) or os.path.getsize(file_path) < 1:
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass
            download_obj.status = "failed"
            download_obj.save()
            return {"status": "failed", "error": "Download produced an empty file."}

        ext = os.path.splitext(file_path)[1] or ".mp4"
        raw_title = (download_obj.title or "download").strip() or "download"
        safe_title = re.sub(r'[/\\?%*:|"<>]', "_", raw_title)[:180].strip() or "download"
        display_name = f"{safe_title}{ext}"

        token = uuid.uuid4()
        download_obj.delivery_token = token
        download_obj.temp_file_path = file_path
        download_obj.delivery_filename = display_name
        download_obj.file_ready_at = timezone.now()
        download_obj.file_size = file_size
        download_obj.status = "completed"
        download_obj.completed_at = timezone.now()
        download_obj.save()

        result = {
            "status": "completed",
            "file_size": file_size,
            "filename": display_name,
            "download_id": download_id,
            "delivery_token": str(token),
        }
        logger.info("Download completed for ID %s", download_id)
        return result

    except Exception as e:
        logger.error("Error in process_media_download for ID %s: %s", download_id, e)
        try:
            download_obj = MediaDownload.objects.get(id=download_id)
            download_obj.status = "failed"
            download_obj.save()
        except Exception:
            pass
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        return {"status": "failed", "error": str(e)}


@shared_task(bind=True, max_retries=2)
def get_media_info_task(self, media_url, user_id=None):
    """Get media information asynchronously"""
    logger.info("Getting media info for URL: %s", media_url)
    downloader = MediaDownloader()

    clean_url = downloader.clean_url(media_url)

    if not downloader.validate_url(clean_url):
        return {"status": "error", "error": "Unsupported URL or platform"}

    try:
        info, error = downloader.extract_media_info(clean_url)

        if error:
            logger.error("Error extracting info: %s", error)
            return {"status": "error", "error": error}

        from django.contrib.auth.models import User

        user = User.objects.get(id=user_id) if user_id else None

        title = _fit(info.get("title"), 500, "Untitled")
        thumbnail = _fit(info.get("thumbnail"), 2048, "")
        duration = _fit(info.get("duration"), 20, "")
        uploader = _fit(info.get("uploader"), 200, "")
        platform = _fit(info.get("platform"), 20, "other")
        media_type = _fit(info.get("media_type"), 10, "video")

        download_obj = MediaDownload.objects.create(
            user=user,
            media_url=clean_url,
            platform=platform,
            media_type=media_type,
            title=title,
            thumbnail=thumbnail,
            duration=duration,
            uploader=uploader,
            user_agent="",
            status="pending",
            metadata={
                "caption": info.get("caption", ""),
                "like_count": info.get("like_count", 0),
                "comment_count": info.get("comment_count", 0),
                "has_multiple": info.get("has_multiple", False),
                "description": info.get("description", ""),
            },
        )

        for fmt in info["formats"]:
            MediaFormat.objects.create(
                download_instance=download_obj,
                resolution=_fit(fmt.get("resolution"), 20, "Unknown"),
                format_id=_fit(fmt.get("format_id"), 50, "best"),
                filesize=_fit(fmt.get("filesize"), 50, "Unknown"),
                extension=_fit(fmt.get("extension"), 10, "mp4"),
                media_type=_fit(fmt.get("type"), 10, media_type),
            )

        logger.info("Media info saved with ID: %s", download_obj.id)
        return {
            "status": "success",
            "download_id": download_obj.id,
            "info": info,
        }

    except Exception as e:
        logger.error("Error in get_media_info_task: %s", e)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=30)
        return {"status": "error", "error": str(e)}
