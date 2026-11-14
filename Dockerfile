FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv \
    SPESE_DATA_DIR=/data

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# The database lives in /data: mount a volume there. Owned by 1000:1000, the
# unprivileged user the container runs as (and the one umbrelOS expects).
RUN mkdir /data && chown 1000:1000 /data
USER 1000:1000
VOLUME /data

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=3)"]

# One worker: SQLite and the in-memory login throttle assume a single process.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
