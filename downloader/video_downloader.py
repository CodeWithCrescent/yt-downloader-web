import yt_dlp
import os
import re
from urllib.parse import urlparse
from django.conf import settings

class VideoDownloader:
    def __init__(self):
        self.temp_dir = settings.DOWNLOAD_TEMP_DIR
    
    def extract_video_info(self, url):
        """Extract video information and available formats"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                video_info = {
                    'title': info.get('title', 'Unknown'),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': self._format_duration(info.get('duration', 0)),
                    'uploader': info.get('uploader', 'Unknown'),
                    'views': info.get('view_count', 0),
                }
                
                # Get available formats (video + audio)
                formats = []
                seen_resolutions = set()
                
                for f in info.get('formats', []):
                    resolution = f.get('height')
                    if resolution and resolution >= 144 and f.get('vcodec') != 'none':
                        # Avoid duplicate resolutions
                        if resolution not in seen_resolutions:
                            seen_resolutions.add(resolution)
                            formats.append({
                                'resolution': f'{resolution}p',
                                'format_id': f.get('format_id'),
                                'filesize': self._format_filesize(f.get('filesize', 0)),
                                'extension': f.get('ext', 'mp4'),
                                'has_audio': f.get('acodec') != 'none'
                            })
                
                # Sort by resolution (highest first)
                formats.sort(key=lambda x: int(x['resolution'].replace('p', '')), reverse=True)
                video_info['formats'] = formats
                
                return video_info, None
                
        except Exception as e:
            return None, str(e)
    
    def download_video(self, url, format_id, video_title):
        """Download video with specific format"""
        # Clean filename
        safe_title = re.sub(r'[^\w\-_\. ]', '_', video_title)
        filename = f"{safe_title}.mp4"
        output_path = os.path.join(self.temp_dir, filename)
        
        ydl_opts = {
            'format': format_id,
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    return output_path, self._format_filesize(file_size), None
                else:
                    return None, None, "Download failed: File not created"
                    
        except Exception as e:
            return None, None, str(e)
    
    def cleanup_temp_file(self, file_path):
        """Remove temporary file"""
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
    
    @staticmethod
    def validate_url(url):
        """Validate video URL"""
        patterns = [
            r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/',
            r'(https?://)?(www\.)?(vimeo\.com)/',
            r'(https?://)?(www\.)?(dailymotion\.com)/',
        ]
        
        for pattern in patterns:
            if re.match(pattern, url):
                return True
        return False
    
    @staticmethod
    def _format_duration(seconds):
        if not seconds:
            return "00:00"
        minutes = seconds // 60
        hours = minutes // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes%60:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    @staticmethod
    def _format_filesize(bytes):
        if not bytes:
            return "Unknown"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.1f} TB"
    