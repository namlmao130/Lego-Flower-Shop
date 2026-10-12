"""Keep in-memory rate limits in one process unless shared storage is configured."""

import os

storage = os.environ.get("RATELIMIT_STORAGE_URI") or os.environ.get("REDIS_URL", "")
workers = (
    max(1, int(os.environ.get("WEB_CONCURRENCY", "2"))) if storage and storage != "memory://" else 1
)
threads = max(1, int(os.environ.get("GUNICORN_THREADS", "2")))
worker_class = "gthread"
timeout = 30
max_requests = 1000
max_requests_jitter = 50
