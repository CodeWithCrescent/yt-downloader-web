# == START COMMANDS ===

python3 -m venv .venv

source .venv/bin/activate

sudo apt-get install redis-server
redis-server

celery -A core worker --loglevel=info

python manage.py runserver

## Optional: Install FFmpeg for better format support

sudo apt-get install ffmpeg


# == RUN NORMAL
nano /etc/systemd/system/ytdownloader-gunicorn.service
/etc/systemd/system/ytdownloader-beat.service
/etc/systemd/system/ytdownloader-worker.service

/etc/docker-setup/traefik/yt-downloader.yml

gunicorn core.wsgi:application --bind 127.0.0.1:9000 --workers 3 --timeout 120

systemctl daemon-reload
systemctl enable --now ytdownloader-gunicorn
systemctl status ytdownloader-gunicorn

systemctl daemon-reload
systemctl enable --now ytdownloader-worker ytdownloader-beat
systemctl status ytdownloader-worker ytdownloader-beat


systemctl restart ytdownloader-worker ytdownloader-beat ytdownloader-gunicorn
systemctl status ytdownloader-worker ytdownloader-beat ytdownloader-gunicorn


# === RESTART APP
sudo systemctl restart ytdownloader-gunicorn

sudo systemctl restart ytdownloader-worker ytdownloader-beat

# ==TODO ==
- [ ] Add country detection (https://country.is/)