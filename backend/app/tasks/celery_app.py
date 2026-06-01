from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "openreef",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.training",
        "app.tasks.maintenance",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

# Periodic maintenance tasks via Celery Beat
# Start beat with: celery -A app.tasks.celery_app beat --loglevel=info
celery_app.conf.beat_schedule = {
    "sync-providers-every-10-min": {
        "task": "app.tasks.maintenance.sync_providers",
        "schedule": 600.0,  # every 10 minutes
    },
    "check-stale-jobs-every-5-min": {
        "task": "app.tasks.maintenance.check_stale_jobs_task",
        "schedule": 300.0,  # every 5 minutes
    },
}
