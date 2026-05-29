from datetime import date
from app.workers.celery_app import celery_app


@celery_app.task
def pre_market_data_sync() -> dict:
    return {"status": "queued", "task": "pre_market_data_sync"}


@celery_app.task
def live_market_scan() -> dict:
    return {"status": "queued", "task": "live_market_scan"}


@celery_app.task
def end_of_day_analytics() -> dict:
    return {"status": "queued", "task": "end_of_day_analytics", "trade_date": str(date.today())}
