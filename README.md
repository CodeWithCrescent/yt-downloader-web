# == START COMMANDS ===

python3 -m venv .venv

source .venv/bin/activate

sudo apt-get install redis-server
redis-server

celery -A core worker --loglevel=info

python manage.py runserver

## Optional: Install FFmpeg for better format support

sudo apt-get install ffmpeg
