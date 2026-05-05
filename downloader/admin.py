from django.contrib import admin
from django.utils.html import format_html
from .models import MediaDownload, MediaFormat, ShareLink, SiteVisit


class MediaFormatInline(admin.TabularInline):
    model = MediaFormat
    fields = ['resolution', 'format_id', 'filesize', 'extension', 'media_type']
    readonly_fields = ['resolution', 'format_id', 'filesize', 'extension', 'media_type']
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(MediaDownload)
class MediaDownloadAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'thumbnail_preview',
        'title_truncated',
        'platform_badge',
        'media_type_badge',
        'status_badge',
        'file_size',
        'ip_address',
        'created_at_formatted'
    ]

    list_filter = [
        'platform',
        'media_type',
        'status',
        ('created_at', admin.DateFieldListFilter),
    ]

    search_fields = [
        'title',
        'media_url',
        'uploader',
        'ip_address',
        'user_agent',
        'referrer',
        'delivery_token',
    ]

    readonly_fields = [
        'media_url',
        'platform',
        'media_type',
        'title',
        'thumbnail_preview_large',
        'duration',
        'uploader',
        'file_size',
        'status',
        'created_at',
        'completed_at',
        'ip_address',
        'user_agent_display',
        'referrer',
        'delivery_token',
        'temp_file_path',
        'delivery_filename',
        'file_ready_at',
        'metadata_display',
        'formats_display',
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': (
                ('media_url', 'platform'),
                ('media_type', 'status'),
                'title',
                'uploader',
            )
        }),
        ('Media Details', {
            'fields': (
                ('thumbnail_preview_large', 'duration'),
                'file_size',
                'metadata_display',
            )
        }),
        ('Visitor Tracking', {
            'fields': (
                'ip_address',
                'user_agent_display',
                'referrer',
            ),
            'classes': ('collapse',)
        }),
        ('Delivery (temporary file)', {
            'fields': (
                'delivery_token',
                'delivery_filename',
                'temp_file_path',
                'file_ready_at',
            ),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': (('created_at', 'completed_at'),),
            'classes': ('collapse',)
        }),
        ('Available Formats', {
            'fields': ('formats_display',),
            'classes': ('wide', 'collapse')
        })
    )

    inlines = [MediaFormatInline]
    actions = ['retry_failed_downloads']
    list_per_page = 25
    date_hierarchy = 'created_at'

    # ---------- Display helpers ----------

    @admin.display(description="Title", ordering='title')
    def title_truncated(self, obj):
        if obj.title and len(obj.title) > 50:
            return obj.title[:47] + '...'
        return obj.title or 'Untitled'

    @admin.display(description="Thumb")
    def thumbnail_preview(self, obj):
        if obj.thumbnail:
            return format_html(
                '<img src="{}" width="60" height="45" style="object-fit: cover; border-radius: 4px;" />',
                obj.thumbnail
            )
        return '<span style="font-size: 24px;">🎬</span>'

    @admin.display(description="Thumbnail")
    def thumbnail_preview_large(self, obj):
        if obj.thumbnail:
            return format_html(
                '<img src="{}" width="240" style="border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />',
                obj.thumbnail
            )
        return '<span style="color: #999;">No thumbnail</span>'

    @admin.display(description="Platform", ordering='platform')
    def platform_badge(self, obj):
        colors = {
            'youtube': '#FF0000',
            'instagram': '#E4405F',
            'facebook': '#1877F2',
            'tiktok': '#000000',
            'pinterest': '#BD081C',
            'twitter': '#1DA1F2',
            'reddit': '#FF4500',
            'vimeo': '#1AB7EA',
            'dailymotion': '#0066DC',
            'twitch': '#9146FF',
            'other': '#666666',
        }
        color = colors.get(obj.platform, '#666666')
        label = dict(obj.PLATFORM_CHOICES).get(obj.platform, obj.platform)

        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, label
        )

    @admin.display(description="Type", ordering='media_type')
    def media_type_badge(self, obj):
        colors = {
            'video': '#3B82F6',
            'image': '#10B981',
            'audio': '#F59E0B',
            'post': '#8B5CF6',
        }
        icons = {
            'video': '🎬',
            'image': '🖼️',
            'audio': '🎵',
            'post': '📝',
        }
        color = colors.get(obj.media_type, '#666666')
        icon = icons.get(obj.media_type, '📄')

        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px;">{} {}</span>',
            color, icon, obj.media_type.title()
        )

    @admin.display(description="Status", ordering='status')
    def status_badge(self, obj):
        colors = {
            'pending': '#F59E0B',
            'processing': '#3B82F6',
            'completed': '#10B981',
            'failed': '#EF4444',
        }
        icons = {
            'pending': '⏳',
            'processing': '🔄',
            'completed': '✅',
            'failed': '❌',
        }
        color = colors.get(obj.status, '#666666')
        icon = icons.get(obj.status, '❓')

        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px;">{} {}</span>',
            color, icon, obj.status.title()
        )

    @admin.display(description="Created", ordering='created_at')
    def created_at_formatted(self, obj):
        return obj.created_at.strftime('%Y-%m-%d %H:%M')

    @admin.display(description="Browser Info")
    def user_agent_display(self, obj):
        if not obj.user_agent:
            return '<span style="color: #999;">—</span>'

        ua = obj.user_agent.lower()

        if 'chrome' in ua and 'edg' not in ua:
            browser = 'Chrome'
        elif 'firefox' in ua:
            browser = 'Firefox'
        elif 'safari' in ua and 'chrome' not in ua:
            browser = 'Safari'
        elif 'edg' in ua:
            browser = 'Edge'
        elif 'opera' in ua or 'opr' in ua:
            browser = 'Opera'
        elif 'mobile' in ua:
            browser = 'Mobile'
        else:
            browser = 'Unknown'

        return format_html(
            '<div style="background: #f8f9fa; padding: 10px; border-radius: 6px; max-width: 500px;">'
            '<p><strong>Browser:</strong> {}</p>'
            '<p style="font-size: 11px; color: #666; margin-top: 5px; word-break: break-all;">{}</p>'
            '</div>',
            browser,
            obj.user_agent[:200]
        )

    @admin.display(description="Metadata")
    def metadata_display(self, obj):
        if not obj.metadata:
            return '<span style="color: #999;">No metadata</span>'

        rows = []
        for key, value in obj.metadata.items():
            if value and not isinstance(value, (dict, list)):
                rows.append(format_html(
                    '<p style="margin: 3px 0;"><strong>{}:</strong> {}</p>',
                    key.replace("_", " ").title(),
                    value
                ))
                
        return format_html(
            '<div style="background: #f8f9fa; padding: 10px; border-radius: 6px;">{}</div>',
            "".join(rows)
        )

    @admin.display(description="Formats")
    def formats_display(self, obj):
        formats = obj.formats.all()
        if not formats:
            return '<span style="color: #999;">No formats</span>'

        cards = []
        for fmt in formats:
            if fmt.media_type == 'video':
                bg, border = '#EFF6FF', '#3B82F6'
            elif fmt.media_type == 'audio':
                bg, border = '#FFFBEB', '#F59E0B'
            else:
                bg, border = '#F0FDF4', '#10B981'

            cards.append(format_html(
                '<div style="background: {}; border-left: 3px solid {}; padding: 8px; border-radius: 4px;">'
                '<strong>{}</strong><br>'
                '<small style="color: #666;">{}</small>'
                '</div>',
                bg, border, fmt.resolution, fmt.filesize
            ))

        return format_html(
            '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 8px;">{}</div>',
            "".join(cards)
        )

    # ---------- Actions ----------

    @admin.action(description='Retry failed downloads')
    def retry_failed_downloads(self, request, queryset):
        from .tasks import process_media_download

        failed = queryset.filter(status='failed')
        count = 0

        for dl in failed:
            fmt = dl.formats.first()
            if fmt:
                process_media_download.delay(dl.id, fmt.format_id)
                count += 1

        self.message_user(request, f'Retrying {count} failed download(s).')

    # ---------- Permissions ----------

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MediaFormat)
class MediaFormatAdmin(admin.ModelAdmin):
    list_display = ['id', 'download_link', 'resolution', 'filesize', 'extension', 'media_type']
    list_filter = ['media_type', 'extension']
    search_fields = ['download_instance__title', 'format_id']
    readonly_fields = ['download_instance', 'resolution', 'format_id', 'filesize', 'extension', 'media_type']

    @admin.display(description="Download")
    def download_link(self, obj):
        return format_html(
            '<a href="/admin/downloader/mediadownload/{}/change/">{}</a>',
            obj.download_instance.id,
            (obj.download_instance.title or 'Untitled')[:40]
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ShareLink)
class ShareLinkAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'channel',
        'token_short',
        'created_at',
        'first_visited_at',
        'visit_count',
        'opened',
    ]
    list_filter = ['channel', ('created_at', admin.DateFieldListFilter)]
    search_fields = ['token']
    readonly_fields = ['token', 'channel', 'created_at', 'first_visited_at', 'visit_count']
    ordering = ['-created_at']

    @admin.display(description='Token')
    def token_short(self, obj):
        return (obj.token[:14] + '…') if len(obj.token) > 14 else obj.token

    @admin.display(description='Link opened?', boolean=True)
    def opened(self, obj):
        return obj.first_visited_at is not None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SiteVisit)
class SiteVisitAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'visited_at',
        'path',
        'from_share',
        'share_channel',
        'ip_address',
        'session_key_short',
    ]
    list_filter = [('visited_at', admin.DateFieldListFilter)]
    search_fields = ['session_key', 'ip_address', 'referrer']
    readonly_fields = [
        'visited_at',
        'path',
        'session_key',
        'ip_address',
        'user_agent',
        'referrer',
        'share_link',
    ]

    @admin.display(description='From share', boolean=True)
    def from_share(self, obj):
        return obj.share_link_id is not None

    @admin.display(description='Share channel')
    def share_channel(self, obj):
        if obj.share_link_id:
            return obj.share_link.get_channel_display()
        return '—'

    @admin.display(description='Session')
    def session_key_short(self, obj):
        s = obj.session_key or ''
        return (s[:10] + '…') if len(s) > 10 else (s or '—')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


admin.site.site_header = 'Video Downloader Admin'
admin.site.site_title = 'Video Downloader Admin'
admin.site.index_title = 'Download Statistics & Management'
