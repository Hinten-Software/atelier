# The NAS's publisher (docs/design-nas-publisher.md): exports the site from the Mac's read-only store, copies it into
# atelier-site, backs the store and the roots up into atelier-backup. Built from a checkout of the repository:
#   docker build -f deploy/nas/publisher/Dockerfile .      (from the checkout's top folder)
FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends rsync tzdata && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir pillow==11.3.0
WORKDIR /app
# only what the export, its scans and the backup read; nothing that paints
COPY runner/ runner/
COPY viewer/ viewer/
COPY site/ site/
COPY tools/whiteroom.py tools/
ENV ATELIER_DATA=/data ATELIER_WORK=/work ATELIER_SITE_OUT=/site ATELIER_BACKUP_OUT=/backup \
    ATELIER_PRIVATE_WORDS=/config/private-words.txt PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
CMD ["python3", "runner/publish.py"]
