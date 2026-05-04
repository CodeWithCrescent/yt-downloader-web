from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('get-media-info/', views.get_media_info, name='get_media_info'),
    path('check-media-status/<str:task_id>/', views.check_media_status, name='check_media_status'),
    path('start-download/', views.start_download, name='start_download'),
    path('check-download-status/<str:task_id>/', views.check_download_status, name='check_download_status'),
    path('download-file/<int:download_id>/', views.download_completed_file, name='download_completed_file'),
    path('my-downloads/', views.my_downloads, name='my_downloads'),
    path('supported-platforms/', views.supported_platforms, name='supported_platforms'),
]