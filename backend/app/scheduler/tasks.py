from datetime import date, datetime, time, timedelta
from app.workers.celery_app import celery_app
from app.analytics.daily import DailyAnalyticsEngine
from app.database.session import SessionLocal
from app.models.entities import ScannedOptionSnapshot
from app.schemas.trading import StrategyConfig
from app.services.alerts import alert_service
from app.services.auth_service import broker_auth_service
from app.services.dhan_scanner import DhanMarketScanner
from app.services.historical_cache import historical_cache_service
from app.services.reconciliation import trade_reconciliation_service


def _is_market_session_now() -> bool:
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    return time(hour=9, minute=15) <= now.time() <= time(hour=15, minute=30)


@celery_app.task
def pre_market_data_sync() -> dict:
    db = SessionLocal()
    try:
        broker = broker_auth_service.ensure_broker(db)
        if not broker:
            return {"status": "skipped", "task": "pre_market_data_sync", "reason": "broker_not_connected"}
        candidate = (
            db.query(ScannedOptionSnapshot)
            .order_by(ScannedOptionSnapshot.timestamp.desc(), ScannedOptionSnapshot.final_trade_score.desc())
            .first()
        )
        if not candidate:
            return {"status": "skipped", "task": "pre_market_data_sync", "reason": "no_candidate"}
        details = candidate.details or {}
        security_id = str(details.get("option_token") or "")
        if not security_id:
            return {"status": "skipped", "task": "pre_market_data_sync", "reason": "candidate_missing_token"}
        today = date.today()
        from_day = today - timedelta(days=10)
        candles = broker.historical_intraday(
            security_id,
            "NSE_FNO",
            str(details.get("instrument") or "OPTSTK"),
            "5",
            f"{from_day.isoformat()} 09:15:00",
            f"{today.isoformat()} 15:30:00",
            oi=True,
        )
        saved = historical_cache_service.save(
            db,
            security_id=security_id,
            exchange_segment="NSE_FNO",
            instrument=str(details.get("instrument") or "OPTSTK"),
            interval="5",
            candles=candles,
        )
        return {"status": "ok", "task": "pre_market_data_sync", "candles": len(candles), "cached_rows": saved}
    finally:
        db.close()


@celery_app.task
def live_market_scan() -> dict:
    if not _is_market_session_now():
        return {"status": "skipped", "task": "live_market_scan", "reason": "outside_market_session"}
    db = SessionLocal()
    try:
        broker = broker_auth_service.ensure_broker(db)
        if not broker:
            return {"status": "skipped", "task": "live_market_scan", "reason": "broker_not_connected"}
        reconciliation = trade_reconciliation_service.reconcile_open_trades(db, broker=broker)
        scan = DhanMarketScanner(broker).scan(db, StrategyConfig(max_trades_per_day=2))
        analytics = DailyAnalyticsEngine().snapshot(db, date.today(), broker=broker)
        candidates = scan.get("candidates") or []
        if candidates:
            best = candidates[0]
            alert_service.send_telegram(
                f"Scanner candidate: {best.get('option_symbol')} score={best.get('final_trade_score')} premium={best.get('premium')}"
            )
        return {
            "status": "ok",
            "task": "live_market_scan",
            "watchlist": len(candidates),
            "sentiment": scan.get("nifty_sentiment") or scan.get("sentiment"),
            "reconciliation": reconciliation,
            "daily_pnl": analytics.get("daily_pnl"),
        }
    finally:
        db.close()


@celery_app.task
def end_of_day_analytics() -> dict:
    db = SessionLocal()
    try:
        broker = broker_auth_service.ensure_broker(db)
        reconciliation = trade_reconciliation_service.reconcile_open_trades(db, broker=broker)
        analytics = DailyAnalyticsEngine().snapshot(db, date.today(), broker=broker)
        return {"status": "ok", "task": "end_of_day_analytics", "trade_date": str(date.today()), "reconciliation": reconciliation, "analytics": analytics}
    finally:
        db.close()
