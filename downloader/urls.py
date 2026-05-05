from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('terms/', views.terms_of_service, name='terms'),
    path('privacy/', views.privacy_policy, name='privacy'),
    path('get-media-info/', views.get_media_info, name='get_media_info'),
    path('check-media-status/<str:task_id>/', views.check_media_status, name='check_media_status'),
    path('start-download/', views.start_download, name='start_download'),
    path('check-download-status/<str:task_id>/', views.check_download_status, name='check_download_status'),
    path('ready/<uuid:token>/<slug:slug>/', views.download_page, name='download_page'),
    path('ready/<uuid:token>/', views.download_page, name='download_page_short'),
    path('file/<uuid:token>/<slug:slug>/', views.download_completed_file, name='download_completed_file'),
    path('file/<uuid:token>/', views.download_completed_file, name='download_completed_file_short'),
    path('download-success/', views.download_success, name='download_success'),
    path('supported-platforms/', views.supported_platforms, name='supported_platforms'),
    path('share/register/', views.register_share, name='register_share'),
]