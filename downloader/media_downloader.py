import yt_dlp
import requests
import os
import re
import json
import uuid
import glob
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from django.conf import settings
from bs4 import BeautifulSoup

class MediaDownloader:
    def __init__(self):
        self.temp_dir = settings.DOWNLOAD_TEMP_DIR
        os.makedirs(self.temp_dir, exist_ok=True)
        self.supported_platforms = {
            'youtube': ['youtube.com', 'youtu.be'],
            'instagram': ['instagram.com', 'instagr.am'],
            'facebook': ['facebook.com', 'fb.watch', 'fb.com'],
            'tiktok': ['tiktok.com', 'vt.tiktok.com'],
            'pinterest': ['pinterest.com', 'pin.it'],
            'twitter': ['twitter.com', 'x.com'],
            'reddit': ['reddit.com', 'redd.it'],
            'vimeo': ['vimeo.com'],
            'dailymotion': ['dailymotion.com'],
            'twitch': ['twitch.tv'],
        }
    
    def clean_url(self, url):
        """Clean URL to get direct media URL (remove playlist, radio params)"""
        parsed = urlparse(url)
        
        # Handle YouTube URLs with extra parameters
        if 'youtube.com' in url or 'youtu.be' in url:
            # Extract video ID
            if 'youtu.be' in url:
                video_id = parsed.path.strip('/')
            else:
                query_params = parse_qs(parsed.query)
                video_id = query_params.get('v', [None])[0]
            
            if video_id:
                # Return clean video URL
                clean_url = f"https://www.youtube.com/watch?v={video_id}"
                return clean_url
        
        # Remove tracking parameters for Instagram
        if 'instagram.com' in url:
            # Remove ?igsh= and other tracking params
            base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
            return base_url
        
        # For other platforms, remove common tracking parameters
        tracking_params = ['utm_', 'ref', 'source', 'fbclid', 'igsh', 'si', 'mt', 'start_radio']
        query_params = parse_qs(parsed.query)
        cleaned_params = {k: v for k, v in query_params.items() 
                         if not any(param in k.lower() for param in tracking_params)}
        
        if cleaned_params:
            cleaned_query = urlencode(cleaned_params, doseq=True)
            clean_url = urlunparse(parsed._replace(query=cleaned_query))
        else:
            clean_url = urlunparse(parsed._replace(query=''))
        
        return clean_url
    
    def detect_platform(self, url):
        """Detect which platform the URL is from"""
        url_lower = url.lower()
        for platform, domains in self.supported_platforms.items():
            for domain in domains:
                if domain in url_lower:
                    return platform
        return 'unknown'
    
    def extract_media_info(self, url):
        """Extract media information based on platform"""
        # Clean URL first
        clean_url = self.clean_url(url)
        platform = self.detect_platform(clean_url)
        
        if platform in ['youtube', 'instagram', 'vimeo', 'dailymotion', 'twitch', 'facebook', 'tiktok']:
            return self._extract_with_ytdlp(clean_url)
        elif platform == 'pinterest':
            return self._extract_pinterest_info(clean_url)
        elif platform == 'twitter':
            return self._extract_twitter_info(clean_url)
        elif platform == 'reddit':
            return self._extract_reddit_info(clean_url)
        else:
            return None, "Unsupported platform or URL"
    
    def _ytdlp_network_opts(self):
        """Anonymous requests only: realistic headers — no cookie files or logins."""
        return {
            'http_headers': {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
                ),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
            },
            'socket_timeout': 60,
        }

    def _flatten_ytdlp_info(self, info):
        """Carousels / multi-entry posts: take first usable leaf."""
        depth = 0
        while info and depth < 12:
            depth += 1
            ents = info.get('entries')
            if ents:
                nxt = next((e for e in ents if e), None)
                if not nxt:
                    return None
                info = nxt
                continue
            break
        return info

    def _extract_with_ytdlp(self, url):
        """Extract info using yt-dlp (YouTube, Instagram, TikTok, Facebook, etc.)."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'ignoreerrors': True,
        }
        ydl_opts.update(self._ytdlp_network_opts())

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if not info:
                    return None, "Could not extract video information"

                info = self._flatten_ytdlp_info(info)
                if not info:
                    return None, "No media found in this link."

                fmts = info.get('formats') or []
                duration = info.get('duration') or 0
                try:
                    duration = int(duration)
                except (TypeError, ValueError):
                    duration = 0
                has_video_track = any(
                    (f.get('vcodec') not in (None, 'none'))
                    for f in fmts
                )
                media_type = 'video' if (duration > 0 or has_video_track) else 'image'
                
                media_info = {
                    'title': info.get('title', 'Unknown'),
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': self._format_duration(info.get('duration', 0)),
                    'uploader': info.get('uploader', 'Unknown'),
                    'platform': self.detect_platform(url),
                    'media_type': media_type,
                }
                
                # Get available formats
                formats = []
                seen_resolutions = set()
                
                if media_type == 'video':
                    for f in info.get('formats', []):
                        resolution = f.get('height')
                        if resolution and resolution >= 144 and f.get('vcodec') != 'none':
                            if resolution not in seen_resolutions:
                                seen_resolutions.add(resolution)
                                file_size = f.get('filesize') or f.get('filesize_approx', 0)
                                formats.append({
                                    'resolution': f'{resolution}p',
                                    'format_id': f.get('format_id'),
                                    'filesize': self._format_filesize(file_size),
                                    'extension': f.get('ext', 'mp4'),
                                    'type': 'video'
                                })
                    
                    # Add best quality format
                    best_format = {
                        'resolution': 'Best Quality',
                        'format_id': 'best',
                        'filesize': 'Unknown',
                        'extension': 'mp4',
                        'type': 'video'
                    }
                    if best_format not in formats:
                        formats.insert(0, best_format)
                    
                    # Also add audio-only formats
                    formats.append({
                        'resolution': 'Audio Only',
                        'format_id': 'bestaudio',
                        'filesize': 'Unknown',
                        'extension': 'mp3',
                        'type': 'audio'
                    })
                else:
                    formats.append({
                        'resolution': 'Original',
                        'format_id': 'best',
                        'filesize': self._format_filesize(info.get('filesize', 0)),
                        'extension': info.get('ext', 'jpg'),
                        'type': media_type
                    })
                
                # Sort formats
                def sort_key(x):
                    if x['resolution'] == 'Best Quality':
                        return 10000
                    elif x['resolution'] == 'Audio Only':
                        return -1
                    else:
                        try:
                            return int(x['resolution'].replace('p', ''))
                        except:
                            return 0
                
                formats.sort(key=sort_key, reverse=True)
                media_info['formats'] = formats
                media_info['has_multiple'] = len(formats) > 1
                
                return media_info, None
                
        except Exception as e:
            return None, str(e)
    
    def _extract_pinterest_info(self, url):
        """Extract Pinterest pins (images and videos)"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                media_type = 'video' if info.get('duration', 0) > 0 else 'image'
                
                media_info = {
                    'title': info.get('title', 'Pinterest Pin')[:100],
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': self._format_duration(info.get('duration', 0)),
                    'uploader': info.get('uploader', 'Pinterest'),
                    'platform': 'pinterest',
                    'media_type': media_type,
                }
                
                formats = [{
                    'resolution': 'Original',
                    'format_id': 'best',
                    'filesize': self._format_filesize(info.get('filesize', 0)),
                    'extension': info.get('ext', 'jpg' if media_type == 'image' else 'mp4'),
                    'type': media_type
                }]
                
                media_info['formats'] = formats
                return media_info, None
                
        except Exception as e:
            return None, str(e)
    
    def _extract_twitter_info(self, url):
        """Extract Twitter/X media"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                media_info = {
                    'title': info.get('title', 'Twitter Post')[:100],
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': self._format_duration(info.get('duration', 0)),
                    'uploader': info.get('uploader', 'Twitter User'),
                    'platform': 'twitter',
                    'media_type': 'video' if info.get('duration', 0) > 0 else 'image',
                }
                
                formats = []
                
                if media_info['media_type'] == 'video':
                    for f in info.get('formats', []):
                        if f.get('vcodec') != 'none' and f.get('height'):
                            formats.append({
                                'resolution': f'{f["height"]}p',
                                'format_id': str(f.get('format_id', 'best')),
                                'filesize': self._format_filesize(f.get('filesize', 0)),
                                'extension': f.get('ext', 'mp4'),
                                'type': 'video'
                            })
                    formats.insert(0, {
                        'resolution': 'Best Quality',
                        'format_id': 'best',
                        'filesize': 'Unknown',
                        'extension': 'mp4',
                        'type': 'video'
                    })
                else:
                    formats.append({
                        'resolution': 'Original',
                        'format_id': 'best',
                        'filesize': self._format_filesize(info.get('filesize', 0)),
                        'extension': info.get('ext', 'jpg'),
                        'type': 'image'
                    })
                
                media_info['formats'] = formats
                return media_info, None
                
        except Exception as e:
            return None, str(e)
    
    def _extract_reddit_info(self, url):
        """Extract Reddit media"""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                media_info = {
                    'title': info.get('title', 'Reddit Post')[:100],
                    'thumbnail': info.get('thumbnail', ''),
                    'duration': self._format_duration(info.get('duration', 0)),
                    'uploader': info.get('uploader', 'Reddit User'),
                    'platform': 'reddit',
                    'media_type': 'video' if info.get('duration', 0) > 0 else 'image',
                }
                
                formats = [{
                    'resolution': 'Original',
                    'format_id': 'best',
                    'filesize': self._format_filesize(info.get('filesize', 0)),
                    'extension': info.get('ext', 'mp4'),
                    'type': media_info['media_type']
                }]
                
                media_info['formats'] = formats
                return media_info, None
                
        except Exception as e:
            return None, str(e)
    
    def download_media(self, url, format_id, title, media_type='video', temp_path=None):
        """Download media to DOWNLOAD_TEMP_DIR using a yt-dlp template (reliable path)."""
        clean_url = self.clean_url(url)
        return self._download_with_ytdlp_to_path(clean_url, format_id, media_type)

    def _pick_ytdlp_output_file(self, out_base):
        """After download, select the main output file next to out_base (no extension)."""
        pattern = out_base + '.*'
        found = []
        for path in glob.glob(pattern):
            pl = path.lower()
            if pl.endswith('.part') or pl.endswith('.ytdl') or pl.endswith('.temp'):
                continue
            if not os.path.isfile(path):
                continue
            try:
                sz = os.path.getsize(path)
            except OSError:
                continue
            if sz < 1:
                continue
            found.append((sz, path))
        if not found:
            return None
        found.sort(key=lambda x: x[0], reverse=True)
        return found[0][1]

    def _download_with_ytdlp_to_path(self, url, format_id, media_type):
        """Download using yt-dlp with %(ext)s template so merges write a real file."""
        uid = uuid.uuid4().hex[:24]
        out_base = os.path.join(self.temp_dir, f'ytdl_{uid}')
        outtmpl = out_base + '.%(ext)s'

        ydl_opts = {
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': False,
            'noplaylist': True,
            'retries': 3,
            'fragment_retries': 3,
        }
        ydl_opts.update(self._ytdlp_network_opts())
        if media_type == 'video':
            ydl_opts['merge_output_format'] = 'mp4'

        if format_id == 'best':
            ydl_opts['format'] = (
                'bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best'
            )
        elif format_id == 'bestaudio':
            ydl_opts['format'] = 'bestaudio/best'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
            ydl_opts.pop('merge_output_format', None)
        else:
            ydl_opts['format'] = format_id

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            output_path = self._pick_ytdlp_output_file(out_base)
            if not output_path:
                return None, None, 'Download failed: no output file (or empty).'

            file_size = os.path.getsize(output_path)
            if file_size < 1:
                try:
                    os.remove(output_path)
                except OSError:
                    pass
                return None, None, 'Download failed: empty file.'

            return output_path, self._format_filesize(file_size), None

        except Exception as e:
            return None, None, str(e)
    
    def _download_with_ytdlp(self, url, format_id, title, media_type):
        """Download using yt-dlp"""
        # Determine extension
        if media_type == 'image':
            extension = 'jpg'
        elif media_type == 'audio' or format_id == 'bestaudio':
            extension = 'mp3'
        else:
            extension = 'mp4'
        
        filename = f"{title}.{extension}"
        output_path = os.path.join(self.temp_dir, filename)
        
        # Configure yt-dlp options
        ydl_opts = {
            'outtmpl': output_path,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        
        # Handle format selection
        if format_id == 'best':
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif format_id == 'bestaudio':
            ydl_opts['format'] = 'bestaudio'
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        else:
            ydl_opts['format'] = format_id
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Download the video
                ydl.download([url])
                
                # Check for downloaded file (yt-dlp might add extension)
                if os.path.exists(output_path):
                    file_size = os.path.getsize(output_path)
                    return output_path, self._format_filesize(file_size), None
                else:
                    # Try to find file with different extension
                    for ext in ['.mp4', '.webm', '.mkv', '.jpg', '.png', '.mp3']:
                        test_path = output_path.replace(f'.{extension}', ext)
                        if os.path.exists(test_path):
                            file_size = os.path.getsize(test_path)
                            return test_path, self._format_filesize(file_size), None
                    
                    return None, None, f"Download failed: File not created at {output_path}"
                    
        except Exception as e:
            return None, None, str(e)
    
    def cleanup_temp_file(self, file_path):
        """Remove temporary file"""
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
    
    @staticmethod
    def validate_url(url):
        """Validate supported URL"""
        # Clean URL first
        if 'youtube.com/watch' in url and 'list=' in url:
            # Extract just the video ID for playlist/radio URLs
            match = re.search(r'[?&]v=([^&]+)', url)
            if match:
                return True
        
        patterns = [
            r'(https?://)?(www\.)?(youtube\.com|youtu\.be)/',
            r'(https?://)?(www\.)?(instagram\.com|instagr\.am)/',
            r'(https?://)?(www\.)?(facebook\.com|fb\.watch)/',
            r'(https?://)?(www\.)?(tiktok\.com|vt\.tiktok\.com)/',
            r'(https?://)?(www\.)?(pinterest\.com|pin\.it)/',
            r'(https?://)?(www\.)?(twitter\.com|x\.com)/',
            r'(https?://)?(www\.)?(reddit\.com|redd\.it)/',
            r'(https?://)?(www\.)?(vimeo\.com)/',
            r'(https?://)?(www\.)?(dailymotion\.com)/',
            r'(https?://)?(www\.)?(twitch\.tv)/',
        ]
        
        for pattern in patterns:
            if re.match(pattern, url):
                return True
        return False
    
    @staticmethod
    def _format_duration(seconds):
        if not seconds or seconds <= 0:
            return "N/A"
        minutes = seconds // 60
        hours = minutes // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes%60:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    @staticmethod
    def _format_filesize(bytes):
        if not bytes or bytes <= 0:
            return "Unknown"
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.1f} TB"
    