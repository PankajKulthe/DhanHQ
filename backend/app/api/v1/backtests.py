from datetime import datetime, time, timedelta
from fastapi import APIRouter, Depends, HTTPException
import pandas as pd
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import ScannedOptionSnapshot
from app.schemas.trading import BacktestRequest
from app.services.auth_service import broker_auth_service
from app.services.historical_cache import historical_cache_service

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("/run")
def run_backtest(payload: BacktestRequest, db: Session = Depends(get_db)) -> dict:
    from app.backtesting.engine import BacktestingEngine

    broker = broker_auth_service.ensure_broker(db)
    if not broker:
        raise HTTPException(status_code=400, detail="Dhan is not connected")

    candidate = None
    security_id = payload.security_id
    option_symbol = payload.option_symbol
    instrument = payload.instrument
    exchange_segment = payload.exchange_segment
    lot_size = payload.lot_size

    if payload.use_latest_candidate and not security_id:
        candidate = (
            db.query(ScannedOptionSnapshot)
            .filter(ScannedOptionSnapshot.eligible.is_(True))
            .order_by(ScannedOptionSnapshot.timestamp.desc(), ScannedOptionSnapshot.final_trade_score.desc())
            .first()
        )
        if not candidate:
            candidate = (
                db.query(ScannedOptionSnapshot)
                .order_by(ScannedOptionSnapshot.timestamp.desc(), ScannedOptionSnapshot.final_trade_score.desc())
                .first()
            )
        if candidate:
            details = candidate.details or {}
            security_id = str(details.get("option_token") or "")
            option_symbol = str(details.get("option_symbol") or candidate.option_symbol)
            lot_size = int(details.get("lot_size") or lot_size or 1)

    if not security_id:
        raise HTTPException(status_code=400, detail="security_id is required, or run scanner first to create a latest candidate")

    from_ts = datetime.combine(payload.from_date, time(hour=9, minute=15))
    to_ts = datetime.combine(payload.to_date, time(hour=15, minute=30))
    candles = historical_cache_service.get(
        db,
        security_id=str(security_id),
        exchange_segment=exchange_segment,
        instrument=instrument,
        interval=payload.interval,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    cache_status = "hit" if candles else "miss"
    cached_rows = len(candles)

    if not candles:
        cursor = payload.from_date
        while cursor <= payload.to_date:
            chunk_end = min(cursor + timedelta(days=89), payload.to_date)
            try:
                candles.extend(
                    broker.historical_intraday(
                        str(security_id),
                        exchange_segment,
                        instrument,
                        payload.interval,
                        f"{cursor.isoformat()} 09:15:00",
                        f"{chunk_end.isoformat()} 15:30:00",
                        oi=True,
                    )
                )
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Dhan historical data failed: {exc}") from exc
            cursor = chunk_end + timedelta(days=1)
        cached_rows = historical_cache_service.save(
            db,
            security_id=str(security_id),
            exchange_segment=exchange_segment,
            instrument=instrument,
            interval=payload.interval,
            candles=candles,
        )

    frame = pd.DataFrame(candles, columns=["ts", "open", "high", "low", "close", "volume", "oi"])
    if not frame.empty:
        frame["ts"] = pd.to_datetime(frame["ts"])
        for column in ["open", "high", "low", "close", "volume", "oi"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0)

    result = BacktestingEngine().run_breakout_backtest(frame, payload, lot_size=lot_size or 1)
    result["source"] = {
        "security_id": str(security_id),
        "option_symbol": option_symbol,
        "exchange_segment": exchange_segment,
        "instrument": instrument,
        "interval": payload.interval,
        "candles": len(candles),
        "historical_cache": cache_status,
        "cached_rows": cached_rows,
        "candidate_used": candidate.details if candidate else None,
    }
    return result
