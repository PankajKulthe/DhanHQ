from datetime import datetime
from sqlalchemy.orm import Session
from app.models.entities import HistoricalDataCache


class HistoricalDataCacheService:
    def get(
        self,
        db: Session,
        *,
        security_id: str,
        exchange_segment: str,
        instrument: str,
        interval: str,
        from_ts: datetime,
        to_ts: datetime,
    ) -> list[list]:
        rows = (
            db.query(HistoricalDataCache)
            .filter(
                HistoricalDataCache.broker == "DHAN",
                HistoricalDataCache.security_id == str(security_id),
                HistoricalDataCache.exchange_segment == exchange_segment,
                HistoricalDataCache.instrument == instrument,
                HistoricalDataCache.interval == str(interval),
                HistoricalDataCache.ts >= from_ts,
                HistoricalDataCache.ts <= to_ts,
            )
            .order_by(HistoricalDataCache.ts.asc())
            .all()
        )
        return [[row.ts.isoformat(), row.open, row.high, row.low, row.close, row.volume, row.oi or 0] for row in rows]

    def save(
        self,
        db: Session,
        *,
        security_id: str,
        exchange_segment: str,
        instrument: str,
        interval: str,
        candles: list[list],
    ) -> int:
        saved = 0
        for candle in candles:
            if len(candle) < 6:
                continue
            try:
                ts = datetime.fromisoformat(str(candle[0]))
            except ValueError:
                continue
            exists = (
                db.query(HistoricalDataCache.id)
                .filter(
                    HistoricalDataCache.broker == "DHAN",
                    HistoricalDataCache.security_id == str(security_id),
                    HistoricalDataCache.exchange_segment == exchange_segment,
                    HistoricalDataCache.instrument == instrument,
                    HistoricalDataCache.interval == str(interval),
                    HistoricalDataCache.ts == ts,
                )
                .first()
            )
            if exists:
                continue
            db.add(
                HistoricalDataCache(
                    broker="DHAN",
                    security_id=str(security_id),
                    exchange_segment=exchange_segment,
                    instrument=instrument,
                    interval=str(interval),
                    ts=ts,
                    open=float(candle[1] or 0),
                    high=float(candle[2] or 0),
                    low=float(candle[3] or 0),
                    close=float(candle[4] or 0),
                    volume=int(candle[5] or 0),
                    oi=int(candle[6] or 0) if len(candle) > 6 else 0,
                )
            )
            saved += 1
        db.commit()
        return saved


historical_cache_service = HistoricalDataCacheService()
