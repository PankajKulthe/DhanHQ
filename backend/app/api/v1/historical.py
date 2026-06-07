from datetime import date, datetime, time, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import ScannedOptionSnapshot
from app.services.auth_service import broker_auth_service
from app.services.dhan_scanner import add_days, cpr_from_candles, numeric, previous_trading_day
from app.services.historical_cache import historical_cache_service

router = APIRouter(prefix="/historical", tags=["historical"])


def _vwap_series(candles: list[list]) -> list[dict]:
    turnover = 0.0
    volume = 0.0
    rows = []
    for candle in candles:
        candle_volume = numeric(candle[5])
        typical = (numeric(candle[2]) + numeric(candle[3]) + numeric(candle[4])) / 3
        turnover += typical * candle_volume
        volume += candle_volume
        rows.append({"ts": candle[0], "value": round(turnover / volume, 2) if volume > 0 else None})
    return rows


def _format_candles(candles: list[list]) -> list[dict]:
    return [
        {
            "ts": str(candle[0]),
            "open": numeric(candle[1]),
            "high": numeric(candle[2]),
            "low": numeric(candle[3]),
            "close": numeric(candle[4]),
            "volume": int(numeric(candle[5])),
            "oi": int(numeric(candle[6])) if len(candle) > 6 else 0,
        }
        for candle in candles
    ]


def _candidate_query(db: Session, universe: str | None):
    query = db.query(ScannedOptionSnapshot)
    if universe:
        query = query.filter(ScannedOptionSnapshot.details["universe"].as_string() == universe)
    return query


@router.get("/latest-candidate")
def latest_candidate(universe: str | None = Query(default=None), db: Session = Depends(get_db)) -> dict:
    candidate = (
        _candidate_query(db, universe)
        .filter(ScannedOptionSnapshot.eligible.is_(True))
        .order_by(ScannedOptionSnapshot.timestamp.desc(), ScannedOptionSnapshot.final_trade_score.desc())
        .first()
    )
    if not candidate:
        candidate = (
            _candidate_query(db, universe)
            .order_by(ScannedOptionSnapshot.timestamp.desc(), ScannedOptionSnapshot.final_trade_score.desc())
            .first()
        )
    if not candidate:
        raise HTTPException(status_code=404, detail="No scanned option candidate found")
    return {
        "timestamp": candidate.timestamp.isoformat(),
        "eligible": candidate.eligible,
        "stock_symbol": candidate.stock_symbol,
        "option_symbol": candidate.option_symbol,
        "option_type": candidate.option_type,
        "security_id": str((candidate.details or {}).get("option_token") or ""),
        "exchange_segment": "NSE_FNO",
        "instrument": str((candidate.details or {}).get("instrument") or "OPTSTK"),
        "details": candidate.details or {},
    }


@router.get("/options")
def option_history(
    security_id: str = Query(...),
    from_date: date = Query(...),
    to_date: date = Query(...),
    interval: str = Query(default="5"),
    exchange_segment: str = Query(default="NSE_FNO"),
    instrument: str = Query(default="OPTSTK"),
    live: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    broker = broker_auth_service.ensure_broker(db)
    if not broker:
        raise HTTPException(status_code=400, detail="Dhan is not connected")
    if from_date > to_date:
        raise HTTPException(status_code=400, detail="from_date must be before to_date")

    daily = interval.upper() in {"1D", "DAY", "DAILY"}
    cache_interval = "1D" if daily else str(interval)
    from_ts = datetime.combine(from_date, time.min if daily else time(hour=9, minute=15))
    to_ts = datetime.combine(to_date, time.max if daily else time(hour=15, minute=30))
    candles = [] if live else historical_cache_service.get(
        db,
        security_id=str(security_id),
        exchange_segment=exchange_segment,
        instrument=instrument,
        interval=cache_interval,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    cache_status = "hit" if candles else "miss"

    if not candles:
        try:
            if daily:
                candles = broker.historical_daily(str(security_id), exchange_segment, instrument, from_date.isoformat(), to_date.isoformat(), oi=True)
            else:
                cursor = from_date
                while cursor <= to_date:
                    chunk_end = min(cursor + timedelta(days=89), to_date)
                    candles.extend(
                        broker.historical_intraday(
                            str(security_id),
                            exchange_segment,
                            instrument,
                            str(interval),
                            f"{cursor.isoformat()} 09:15:00",
                            f"{chunk_end.isoformat()} 15:30:00",
                            oi=True,
                        )
                    )
                    cursor = chunk_end + timedelta(days=1)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Dhan historical option data failed: {exc}") from exc
        historical_cache_service.save(
            db,
            security_id=str(security_id),
            exchange_segment=exchange_segment,
            instrument=instrument,
            interval=cache_interval,
            candles=candles,
        )
        cache_status = "refresh" if live else "miss_saved"

    cpr_day = previous_trading_day(from_date)
    try:
        cpr_source = broker.historical_daily(str(security_id), exchange_segment, instrument, cpr_day.isoformat(), add_days(cpr_day, 1), oi=True)
        cpr = cpr_from_candles(cpr_source[-1:], f"PREVIOUS_DAY_{cpr_day.isoformat()}") or {}
    except Exception:
        cpr = {}
    quote = {}
    if live:
        try:
            quote = broker.quote_many(exchange_segment, [security_id]).get(str(security_id), {})
        except Exception:
            quote = {}

    return {
        "security_id": str(security_id),
        "exchange_segment": exchange_segment,
        "instrument": instrument,
        "interval": cache_interval,
        "from_date": from_date.isoformat(),
        "to_date": to_date.isoformat(),
        "live": live,
        "cache": cache_status,
        "candles": _format_candles(candles),
        "vwap": _vwap_series(candles),
        "cpr": {
            "date": cpr_day.isoformat(),
            "pivot": numeric(cpr.get("pivot")),
            "bc": numeric(cpr.get("bc")),
            "tc": numeric(cpr.get("tc")),
            "source": cpr.get("source") or "UNAVAILABLE",
        },
        "quote": quote,
    }
