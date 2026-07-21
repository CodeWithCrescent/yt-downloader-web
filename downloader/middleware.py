import logging
from datetime import date

from django.utils import timezone

from .models import ShareLink, SiteVisit

logger = logging.getLogger(__name__)

TRACKED_PATHS = frozenset({"/", "/terms/", "/privacy/"})


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or None


def _track_share_link_hit(request):
    token = (request.GET.get("s") or "")[:64]
    if not token:
        return None
    try:
        sl = ShareLink.objects.get(token=token)
    except ShareLink.DoesNotExist:
        return None
    now = timezone.now()
    if sl.first_visited_at is None:
        sl.first_visited_at = now
    sl.visit_count += 1
    sl.save(update_fields=["first_visited_at", "visit_count"])
    return sl


def _session_key_string(request):
    key = getattr(request.session, "session_key", None) or ""
    return key[:40] if key else ""


def _maybe_log_site_visit(request, share_link):
    if request.method != "GET":
        return
    path = request.path or "/"
    if path not in TRACKED_PATHS:
        return

    today = date.today().isoformat()
    path_key = (path.strip("/") or "home").replace("/", "-")
    session_key = f"sv_tracked_{today}_{path_key}"
    if request.session.get(session_key):
        return

    try:
        request.session[session_key] = True
        request.session.modified = True
        SiteVisit.objects.create(
            path=path,
            session_key=_session_key_string(request),
            ip_address=get_client_ip(request),
            user_agent=(request.META.get("HTTP_USER_AGENT", "") or "")[:512],
            referrer=(request.META.get("HTTP_REFERER", "") or "")[:500],
            share_link=share_link,
        )
    except Exception:
        logger.exception("Site visit logging failed")


class VisitTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        share_link = None
        if request.method == "GET":
            try:
                share_link = _track_share_link_hit(request)
            except Exception:
                logger.exception("Share link hit tracking failed")
            try:
                _maybe_log_site_visit(request, share_link)
            except Exception:
                logger.exception("Site visit middleware failed")

        return self.get_response(request)
