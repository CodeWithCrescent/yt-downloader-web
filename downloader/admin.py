# from django.contrib import admin
# from django.utils.html import format_html
# from django.urls import reverse
# from .models import MediaDownload, MediaFormat


# class MediaFormatInline(admin.TabularInline):
#     """Inline display of media formats within a download record"""
#     model = MediaFormat
#     fields = ['resolution', 'format_id', 'filesize', 'extension', 'media_type']
#     readonly_fields = ['resolution', 'format_id', 'filesize', 'extension', 'media_type']
#     extra = 0
#     can_delete = False
#     max_num = 0
#     show_change_link = False
    
#     def has_add_permission(self, request, obj=None):
#         return False
    
#     def has_delete_permission(self, request, obj=None):
#         return False


# @admin.register(MediaDownload)
# class MediaDownloadAdmin(admin.ModelAdmin):
#     # List view configuration
#     list_display = [
#         'id', 
#         'thumbnail_preview', 
#         'title_truncated', 
#         'platform_badge', 
#         'media_type_badge',
#         'status_badge', 
#         'file_size', 
#         'user_info', 
#         'created_at_formatted'
#     ]
    
#     list_filter = [
#         'platform', 
#         'media_type', 
#         'status', 
#         ('created_at', admin.DateFieldListFilter),
#         'user'
#     ]
    
#     search_fields = [
#         'title', 
#         'media_url', 
#         'uploader', 
#         'user__username', 
#         'user__email'
#     ]
    
#     readonly_fields = [
#         'media_url',
#         'platform',
#         'media_type', 
#         'title',
#         'thumbnail_preview_large',
#         'duration',
#         'uploader',
#         'file_path',
#         'file_size',
#         'created_at',
#         'completed_at',
#         'metadata_display',
#         'formats_display'
#     ]
    
#     fieldsets = (
#         ('Basic Information', {
#             'fields': (
#                 ('media_url', 'platform'),
#                 ('media_type', 'status'),
#                 'title',
#                 'uploader',
#             )
#         }),
#         ('Media Details', {
#             'fields': (
#                 ('thumbnail_preview_large', 'duration'),
#                 ('file_path', 'file_size'),
#                 'metadata_display'
#             )
#         }),
#         ('Timestamps', {
#             'fields': (('created_at', 'completed_at'),),
#             'classes': ('collapse',)
#         }),
#         ('Available Formats', {
#             'fields': ('formats_display',),
#             'classes': ('wide',)
#         })
#     )
    
#     inlines = [MediaFormatInline]
    
#     actions = ['retry_failed_downloads', 'delete_selected']
    
#     # Customize list view
#     list_per_page = 20
#     list_max_show_all = 100
#     date_hierarchy = 'created_at'
    
#     def get_queryset(self, request):
#         """Optimize queryset with select_related for user"""
#         return super().get_queryset(request).select_related('user')
    
#     # Custom column methods
#     def title_truncated(self, obj):
#         """Truncate long titles"""
#         if len(obj.title) > 50:
#             return obj.title[:47] + '...'
#         return obj.title
#     title_truncated.short_description = 'Title'
#     title_truncated.admin_order_field = 'title'
    
#     def thumbnail_preview(self, obj):
#         """Show thumbnail preview in list view"""
#         if obj.thumbnail:
#             return format_html(
#                 '<img src="{}" width="50" height="38" style="object-fit: cover; border-radius: 4px;" />',
#                 obj.thumbnail
#             )
#         return format_html(
#             '<div style="width: 50px; height: 38px; background: #f0f0f0; display: flex; align-items: center; justify-content: center; border-radius: 4px;">'
#             '<span style="font-size: 20px;">🎬</span></div>'
#         )
#     thumbnail_preview.short_description = 'Thumb'
#     thumbnail_preview.admin_order_field = 'thumbnail'
    
#     def thumbnail_preview_large(self, obj):
#         """Show larger thumbnail in detail view"""
#         if obj.thumbnail:
#             return format_html(
#                 '<img src="{}" width="200" style="border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />',
#                 obj.thumbnail
#             )
#         return format_html('<div style="color: #999;">No thumbnail available</div>')
#     thumbnail_preview_large.short_description = 'Thumbnail'
    
#     def platform_badge(self, obj):
#         """Display platform with colored badge"""
#         platform_colors = {
#             'youtube': ('#FF0000', 'YouTube'),
#             'instagram': ('#E4405F', 'Instagram'),
#             'facebook': ('#1877F2', 'Facebook'),
#             'tiktok': ('#000000', 'TikTok'),
#             'pinterest': ('#BD081C', 'Pinterest'),
#             'twitter': ('#1DA1F2', 'Twitter/X'),
#             'reddit': ('#FF4500', 'Reddit'),
#             'vimeo': ('#1AB7EA', 'Vimeo'),
#             'dailymotion': ('#0066DC', 'Dailymotion'),
#             'twitch': ('#9146FF', 'Twitch'),
#             'other': ('#666666', 'Other'),
#         }
#         color, name = platform_colors.get(obj.platform, platform_colors['other'])
#         return format_html(
#             '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
#             color, name
#         )
#     platform_badge.short_description = 'Platform'
#     platform_badge.admin_order_field = 'platform'
    
#     def media_type_badge(self, obj):
#         """Display media type with icon"""
#         type_icons = {
#             'video': ('#3B82F6', '🎬 Video'),
#             'image': ('#10B981', '🖼️ Image'),
#             'audio': ('#F59E0B', '🎵 Audio'),
#             'post': ('#8B5CF6', '📝 Post'),
#         }
#         color, display = type_icons.get(obj.media_type, ('#666666', obj.media_type))
#         return format_html(
#             '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
#             color, display
#         )
#     media_type_badge.short_description = 'Type'
#     media_type_badge.admin_order_field = 'media_type'
    
#     def status_badge(self, obj):
#         """Display status with appropriate color"""
#         status_colors = {
#             'pending': ('#F59E0B', '⏳ Pending'),
#             'processing': ('#3B82F6', '🔄 Processing'),
#             'completed': ('#10B981', '✅ Completed'),
#             'failed': ('#EF4444', '❌ Failed'),
#         }
#         color, display = status_colors.get(obj.status, ('#666666', obj.status))
#         return format_html(
#             '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 12px; font-size: 11px;">{}</span>',
#             color, display
#         )
#     status_badge.short_description = 'Status'
#     status_badge.admin_order_field = 'status'
    
#     def user_info(self, obj):
#         """Display user information with link"""
#         if obj.user:
#             url = reverse('admin:auth_user_change', args=[obj.user.id])
#             return format_html(
#                 '<a href="{}" style="font-weight: 500;">{}</a><br><span style="font-size: 10px; color: #666;">{}</span>',
#                 url, obj.user.username, obj.user.email or 'No email'
#             )
#         return format_html('<span style="color: #999;">Anonymous</span>')
#     user_info.short_description = 'User'
#     user_info.admin_order_field = 'user__username'
    
#     def created_at_formatted(self, obj):
#         """Format created_at for better display"""
#         return obj.created_at.strftime('%Y-%m-%d %H:%M')
#     created_at_formatted.short_description = 'Created'
#     created_at_formatted.admin_order_field = 'created_at'
    
#     def metadata_display(self, obj):
#         """Display metadata in a readable format"""
#         if not obj.metadata:
#             return format_html('<div style="color: #999;">No metadata available</div>')
        
#         html = '<div style="background: #f8f9fa; padding: 10px; border-radius: 6px;">'
        
#         # Display Instagram-specific metadata
#         if obj.platform == 'instagram':
#             if obj.metadata.get('caption'):
#                 html += f'<p><strong>📝 Caption:</strong><br>{obj.metadata["caption"][:200]}</p>'
#             if obj.metadata.get('like_count'):
#                 html += f'<p><strong>❤️ Likes:</strong> {obj.metadata["like_count"]:,}</p>'
#             if obj.metadata.get('comment_count'):
#                 html += f'<p><strong>💬 Comments:</strong> {obj.metadata["comment_count"]:,}</p>'
#             if obj.metadata.get('has_multiple'):
#                 html += '<p><strong>📸 Multiple Media:</strong> Yes</p>'
        
#         # Display other metadata
#         for key, value in obj.metadata.items():
#             if key not in ['caption', 'like_count', 'comment_count', 'has_multiple']:
#                 if isinstance(value, dict) or isinstance(value, list):
#                     continue  # Skip complex structures
#                 html += f'<p><strong>{key.replace("_", " ").title()}:</strong> {value}</p>'
        
#         html += '</div>'
#         return format_html(html)
#     metadata_display.short_description = 'Additional Metadata'
    
#     def formats_display(self, obj):
#         """Display available formats in a grid"""
#         formats = obj.formats.all()
#         if not formats:
#             return format_html('<div style="color: #999;">No formats available</div>')
        
#         html = '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px;">'
        
#         for fmt in formats:
#             # Determine color based on media type
#             if fmt.media_type == 'video':
#                 bg_color = '#EFF6FF'
#                 border_color = '#3B82F6'
#                 icon = '🎬'
#             elif fmt.media_type == 'audio':
#                 bg_color = '#FFFBEB'
#                 border_color = '#F59E0B'
#                 icon = '🎵'
#             else:
#                 bg_color = '#F0FDF4'
#                 border_color = '#10B981'
#                 icon = '🖼️'
            
#             html += f'''
#                 <div style="background-color: {bg_color}; border-left: 3px solid {border_color}; padding: 8px; border-radius: 4px;">
#                     <div style="font-weight: bold; font-size: 14px;">{icon} {fmt.resolution}</div>
#                     <div style="font-size: 11px; color: #666;">Format: {fmt.format_id}</div>
#                     <div style="font-size: 11px; color: #666;">Size: {fmt.filesize}</div>
#                     <div style="font-size: 11px; color: #666;">Ext: {fmt.extension}</div>
#                 </div>
#             '''
        
#         html += '</div>'
#         return format_html(html)
#     formats_display.short_description = 'Available Formats'
    
#     # Custom actions
#     def retry_failed_downloads(self, request, queryset):
#         """Retry failed downloads"""
#         from .tasks import process_media_download
        
#         failed_downloads = queryset.filter(status='failed')
#         count = 0
        
#         for download in failed_downloads:
#             # Get the best format
#             best_format = download.formats.first()
#             if best_format:
#                 process_media_download.delay(download.id, best_format.format_id)
#                 count += 1
        
#         self.message_user(request, f'Started retry for {count} failed download(s).')
#     retry_failed_downloads.short_description = 'Retry selected failed downloads'
    
#     # Override delete_selected to show confirmation
#     def delete_selected(self, request, queryset):
#         """Delete selected items with cleanup"""
#         count = queryset.count()
#         for obj in queryset:
#             # Delete file from storage if exists
#             if obj.file_path:
#                 try:
#                     obj.file_path.delete(save=False)
#                 except:
#                     pass
#         super().delete_selected(request, queryset)
#         self.message_user(request, f'Successfully deleted {count} download(s).')
#     delete_selected.short_description = 'Delete selected downloads'
    
#     # Permissions
#     def has_add_permission(self, request):
#         """Disable manual addition of downloads through admin"""
#         return False
    
#     def has_change_permission(self, request, obj=None):
#         """Allow only status changes"""
#         if obj and request.user.has_perm('downloader.change_mediadownload'):
#             return True
#         return super().has_change_permission(request, obj)


# @admin.register(MediaFormat)
# class MediaFormatAdmin(admin.ModelAdmin):
#     list_display = ['id', 'download_link', 'resolution', 'filesize', 'extension', 'media_type']
#     list_filter = ['resolution', 'media_type', 'extension']
#     search_fields = ['download_instance__title', 'format_id']
#     readonly_fields = ['download_instance', 'resolution', 'format_id', 'filesize', 'extension', 'media_type']
    
#     def download_link(self, obj):
#         """Link to parent download record"""
#         url = reverse('admin:downloader_mediadownload_change', args=[obj.download_instance.id])
#         return format_html('<a href="{}">{}</a>', url, obj.download_instance.title[:50])
#     download_link.short_description = 'Parent Download'
    
#     def has_add_permission(self, request):
#         return False
    
#     def has_change_permission(self, request, obj=None):
#         return False
    
#     def has_delete_permission(self, request, obj=None):
#         return False


# # Custom admin site configuration
# admin.site.site_header = 'Video Downloader Admin Panel'
# admin.site.site_title = 'Video Downloader Admin'
# admin.site.index_title = 'Welcome to Media Downloader Administration'
# admin.site.empty_value_display = '— Not provided —'
