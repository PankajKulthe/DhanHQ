from datetime import datetime
from typing import Any
from sqlalchemy.orm import Session
from app.models.entities import Position, Trade, TradeLog
from app.services.alerts import alert_service


COMPLETED_STATUSES = {"TRADED", "COMPLETE", "COMPLETED", "FILLED"}


def _order_id(order: dict[str, Any]) -> str:
    return str(order.get("orderId") or order.get("order_id") or order.get("id") or "")


def _order_status(order: dict[str, Any]) -> str:
    return str(order.get("orderStatus") or order.get("order_status") or order.get("status") or "").upper()


def _average_price(order: dict[str, Any]) -> float:
    for key in ("averageTradedPrice", "averagePrice", "tradedPrice", "price"):
        try:
            value = float(order.get(key) or 0)
        except (TypeError, ValueError):
            value = 0
        if value > 0:
            return value
    return 0.0


class TradeReconciliationService:
    def reconcile_open_trades(self, db: Session, broker=None) -> dict:
        if not broker:
            return {"status": "skipped", "reason": "broker_not_connected", "closed": 0}
        open_trades = db.query(Trade).filter(Trade.status == "OPEN").all()
        if not open_trades:
            return {"status": "ok", "closed": 0}

        order_book = { _order_id(order): order for order in broker.orders() if _order_id(order) }
        closed = 0
        for trade in open_trades:
            exit_order = order_book.get(str(trade.sl_order_id or ""))
            if not exit_order or _order_status(exit_order) not in COMPLETED_STATUSES:
                continue
            exit_price = _average_price(exit_order) or float(trade.stop_loss or trade.entry_price or 0)
            trade.exit_price = exit_price
            trade.realized_pnl = (exit_price - float(trade.entry_price or 0)) * int(trade.quantity or 0)
            trade.status = "CLOSED"
            trade.closed_at = datetime.utcnow()
            db.query(Position).filter(Position.trade_id == trade.id).update(
                {
                    Position.status: "CLOSED",
                    Position.ltp: exit_price,
                    Position.unrealized_pnl: 0.0,
                }
            )
            db.add(
                TradeLog(
                    trade_id=trade.id,
                    event_type="EXIT_RECONCILED",
                    message=f"Dhan exit reconciled at {exit_price}",
                    payload={"order": exit_order},
                )
            )
            alert_service.send_telegram(f"EXIT {trade.mode} trade_id={trade.id} exit={exit_price} pnl={round(trade.realized_pnl, 2)}")
            closed += 1
        db.commit()
        return {"status": "ok", "closed": closed, "open_checked": len(open_trades)}


trade_reconciliation_service = TradeReconciliationService()
