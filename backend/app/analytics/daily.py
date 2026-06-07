from datetime import date
from datetime import datetime, time
from sqlalchemy.orm import Session
from app.models.entities import (
    FilteredStockSnapshot,
    MarketSentiment,
    OptionWatchlistSnapshot,
    Position,
    ScannedOptionSnapshot,
    Symbol,
    StockSentimentSnapshot,
    Trade,
)
from app.services.dhan_scanner import normalize_quote


class DailyAnalyticsEngine:
    def _refresh_unrealized_pnl(self, db: Session, broker=None) -> float:
        open_positions = (
            db.query(Position, Symbol)
            .join(Symbol, Position.symbol_id == Symbol.id)
            .filter(Position.status == "OPEN")
            .all()
        )
        if not open_positions:
            return 0.0

        by_segment: dict[str, list[str]] = {}
        for _position, symbol in open_positions:
            exchange = (symbol.exchange or "").upper()
            segment = "NSE_FNO" if exchange in {"NFO", "NSE_FNO"} else "NSE_EQ"
            if symbol.token:
                by_segment.setdefault(segment, []).append(str(symbol.token))

        quotes: dict[str, dict] = {}
        if broker:
            for segment, security_ids in by_segment.items():
                try:
                    quotes.update(broker.quote_many(segment, security_ids))
                except Exception:
                    continue

        total = 0.0
        for position, symbol in open_positions:
            quote = normalize_quote(quotes.get(str(symbol.token)))
            ltp = float(quote.get("ltp") or position.ltp or position.avg_price or 0)
            position.ltp = ltp
            position.unrealized_pnl = (ltp - float(position.avg_price or 0)) * int(position.quantity or 0)
            total += float(position.unrealized_pnl or 0)
        db.commit()
        return total

    def snapshot(self, db: Session, trade_date: date, broker=None) -> dict:
        start = datetime.combine(trade_date, time.min)
        end = datetime.combine(trade_date, time.max)
        latest_sentiment = (
            db.query(MarketSentiment)
            .filter(MarketSentiment.timestamp >= start, MarketSentiment.timestamp <= end)
            .order_by(MarketSentiment.timestamp.desc())
            .first()
        )
        latest_scan_ts = latest_sentiment.timestamp if latest_sentiment else None
        recent_options_query = db.query(ScannedOptionSnapshot)
        if latest_scan_ts:
            recent_options_query = recent_options_query.filter(ScannedOptionSnapshot.timestamp == latest_scan_ts)
        else:
            recent_options_query = recent_options_query.filter(ScannedOptionSnapshot.timestamp >= start, ScannedOptionSnapshot.timestamp <= end)
        recent_options = recent_options_query.order_by(
            ScannedOptionSnapshot.eligible.desc(),
            ScannedOptionSnapshot.final_trade_score.desc(),
            ScannedOptionSnapshot.volume.desc(),
        ).limit(25).all()
        best_candidate = next((row for row in recent_options if row.eligible), recent_options[0] if recent_options else None)
        trades = db.query(Trade).filter(Trade.opened_at >= start, Trade.opened_at <= end).all()
        realized_pnl = sum(float(t.realized_pnl or 0) for t in trades)
        open_unrealized = self._refresh_unrealized_pnl(db, broker=broker)
        daily_pnl = realized_pnl + open_unrealized
        wins = [t for t in trades if float(t.realized_pnl or 0) > 0]
        losses = [t for t in trades if float(t.realized_pnl or 0) < 0]
        scanned_options_today = db.query(ScannedOptionSnapshot).filter(ScannedOptionSnapshot.timestamp >= start, ScannedOptionSnapshot.timestamp <= end).count()
        stock_sentiments_today = db.query(StockSentimentSnapshot).filter(StockSentimentSnapshot.timestamp >= start, StockSentimentSnapshot.timestamp <= end).count()
        filtered_rows_today = db.query(FilteredStockSnapshot).filter(FilteredStockSnapshot.timestamp >= start, FilteredStockSnapshot.timestamp <= end).count()
        latest_filtered_count = 0
        if latest_scan_ts:
            latest_filtered_count = (
                db.query(FilteredStockSnapshot)
                .filter(FilteredStockSnapshot.timestamp == latest_scan_ts, FilteredStockSnapshot.event.in_(["ENTER_FILTER", "ACTIVE_FILTER"]))
                .count()
            )
        watchlist_today = db.query(OptionWatchlistSnapshot).filter(OptionWatchlistSnapshot.timestamp >= start, OptionWatchlistSnapshot.timestamp <= end).count()
        return {
            "trade_date": str(trade_date),
            "stocks_moved_gt_2pct": latest_filtered_count,
            "nifty_breadth_score": (latest_sentiment.bullish_count - latest_sentiment.bearish_count) if latest_sentiment else 0,
            "sentiment": latest_sentiment.final_sentiment if latest_sentiment else "UNKNOWN",
            "trades_executed": len(trades),
            "daily_pnl": round(daily_pnl, 2),
            "realized_pnl": round(realized_pnl, 2),
            "unrealized_pnl": round(open_unrealized, 2),
            "wins": len(wins),
            "losses": len(losses),
            "latest_scan_at": latest_scan_ts.isoformat() if latest_scan_ts else None,
            "bullish_count": latest_sentiment.bullish_count if latest_sentiment else 0,
            "bearish_count": latest_sentiment.bearish_count if latest_sentiment else 0,
            "neutral_count": latest_sentiment.neutral_count if latest_sentiment else 0,
            "storage": {
                "market_sentiment_rows": db.query(MarketSentiment).count(),
                "stock_sentiment_rows_today": stock_sentiments_today,
                "scanned_option_rows_today": scanned_options_today,
                "filtered_stock_rows_today": filtered_rows_today,
                "option_watchlist_rows_today": watchlist_today,
                "trade_rows_today": len(trades),
            },
            "best_candidate": best_candidate.details if best_candidate else None,
            "recent_scanned_options": [row.details for row in recent_options],
            "recent_trades": [
                {
                    "id": trade.id,
                    "mode": trade.mode,
                    "status": trade.status,
                    "entry_price": trade.entry_price,
                    "stop_loss": trade.stop_loss,
                    "target": trade.target,
                    "realized_pnl": trade.realized_pnl,
                    "opened_at": trade.opened_at.isoformat() if trade.opened_at else None,
                    "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
                }
                for trade in trades[-20:]
            ],
        }
