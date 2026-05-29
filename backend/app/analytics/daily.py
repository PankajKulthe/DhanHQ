from datetime import date
from sqlalchemy.orm import Session
from app.models.entities import DailyOptionActivity, NiftySentiment, Trade


class DailyAnalyticsEngine:
    def snapshot(self, db: Session, trade_date: date) -> dict:
        moved = db.query(DailyOptionActivity).filter(DailyOptionActivity.trade_date == trade_date).count()
        sentiment = db.query(NiftySentiment).filter(NiftySentiment.trade_date == trade_date).order_by(NiftySentiment.created_at.desc()).first()
        trades = db.query(Trade).filter(Trade.opened_at >= trade_date).all()
        pnl = sum(t.realized_pnl for t in trades)
        return {
            "trade_date": str(trade_date),
            "stocks_moved_gt_2pct": moved,
            "nifty_breadth_score": sentiment.breadth_score if sentiment else 0,
            "sentiment": sentiment.sentiment if sentiment else "UNKNOWN",
            "trades_executed": len(trades),
            "daily_pnl": round(pnl, 2),
            "wins": len([t for t in trades if t.realized_pnl > 0]),
            "losses": len([t for t in trades if t.realized_pnl < 0]),
        }
