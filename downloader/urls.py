from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('get-video-info/', views.get_video_info, name='get_video_info'),
    path('check-video-status/<str:task_id>/', views.check_video_status, name='check_video_status'),
    path('start-download/', views.start_download, name='start_download'),
    path('check-download-status/<str:task_id>/', views.check_download_status, name='check_download_status'),
    path('my-downloads/', views.my_downloads, name='my_downloads'),
    path('download-file/<int:download_id>/', views.download_file, name='download_file'),
]
