from celery import Celery
from app.core.config import get_settings

settings = get_settings()
celery_app = Celery(
    "trading",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.scheduler.tasks"],
)
celery_app.conf.timezone = "Asia/Kolkata"
celery_app.conf.imports = ("app.scheduler.tasks",)
celery_app.conf.beat_schedule = {
    "pre-market-data-sync": {"task": "app.scheduler.tasks.pre_market_data_sync", "schedule": 60 * 60},
    "live-market-scan": {"task": "app.scheduler.tasks.live_market_scan", "schedule": 60},
    "end-of-day-analytics": {"task": "app.scheduler.tasks.end_of_day_analytics", "schedule": 60 * 60},
}

import app.scheduler.tasks  # noqa: E402,F401
