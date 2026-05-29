from datetime import datetime
import pandas as pd
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from app.models.entities import HistoricalCandle, Symbol


NIFTY_50 = {
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE",
    "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY",
    "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO",
    "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT",
    "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN",
    "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL", "TECHM", "TITAN",
    "TRENT", "ULTRACEMCO", "WIPRO",
}


class HistoricalDataEngine:
    def __init__(self, broker):
        self.broker = broker

    def fetch_candles(self, symbol: Symbol, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        raw = self.broker.candle_data(symbol.exchange, symbol.token, timeframe, start.strftime("%Y-%m-%d %H:%M"), end.strftime("%Y-%m-%d %H:%M"))
        df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
        if df.empty:
            return df
        df["ts"] = pd.to_datetime(df["ts"])
        return df

    def persist_candles(self, db: Session, symbol: Symbol, timeframe: str, candles: pd.DataFrame) -> int:
        rows = [
            {
                "symbol_id": symbol.id,
                "timeframe": timeframe,
                "ts": row.ts.to_pydatetime(),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": int(row.volume or 0),
            }
            for row in candles.itertuples(index=False)
        ]
        if not rows:
            return 0
        stmt = insert(HistoricalCandle).values(rows)
        stmt = stmt.on_conflict_do_nothing(index_elements=["symbol_id", "timeframe", "ts"])
        db.execute(stmt)
        db.commit()
        return len(rows)


class StockFilteringEngine:
    def filter_by_move(self, snapshots: list[dict], min_abs_change_pct: float = 2.0) -> list[dict]:
        filtered = []
        for item in snapshots:
            prev_close = float(item.get("previous_close") or 0)
            ltp = float(item.get("ltp") or 0)
            if prev_close <= 0:
                continue
            change = ((ltp - prev_close) / prev_close) * 100
            if abs(change) >= min_abs_change_pct:
                filtered.append({**item, "change_pct": round(change, 2), "bias": "BULLISH" if change > 0 else "BEARISH"})
        return filtered
