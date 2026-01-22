"""Celery application configuration."""
import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

# Create Celery app
celery_app = Celery(
    "receipt_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["worker.tasks"],
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour max
    task_soft_time_limit=3300,  # 55 minutes soft limit
    worker_prefetch_multiplier=1,
    worker_concurrency=4,
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "sync-all-accounts-hourly": {
        "task": "worker.tasks.sync_all_accounts_task",
        "schedule": 3600.0,  # Every hour
    },
}
