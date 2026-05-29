import logging
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.entities import Position, Trade, TradeLog
from app.risk.manager import RiskDecision

logger = logging.getLogger(__name__)


class ExecutionEngine:
    def __init__(self, broker=None):
        self.broker = broker

    def place_market_buy_with_sl(self, db: Session, *, symbol_id: int, trading_symbol: str, token: str, quantity: int, entry_price: float, stop_loss: float, target: float | None, strategy_name: str, mode: str, idempotency_key: str, risk: RiskDecision) -> Trade:
        settings = get_settings()
        if mode == "LIVE" and not settings.live_trading_enabled:
            raise PermissionError("LIVE trading is disabled by configuration")
        trade = Trade(idempotency_key=idempotency_key, mode=mode, strategy_name=strategy_name, symbol_id=symbol_id, side="BUY", quantity=quantity, entry_price=entry_price, stop_loss=stop_loss, target=target)
        try:
            db.add(trade)
            db.flush()
        except IntegrityError:
            db.rollback()
            existing = db.query(Trade).filter(Trade.idempotency_key == idempotency_key).one()
            return existing
        if mode == "LIVE":
            payload = {
                "variety": "NORMAL",
                "tradingsymbol": trading_symbol,
                "symboltoken": token,
                "transactiontype": "BUY",
                "exchange": "NFO",
                "ordertype": "MARKET",
                "producttype": "CARRYFORWARD",
                "duration": "DAY",
                "quantity": str(quantity),
            }
            trade.broker_order_id = self.broker.place_order(payload)
            sl_payload = {**payload, "transactiontype": "SELL", "ordertype": "STOPLOSS_LIMIT", "price": str(risk.sl_limit_price), "triggerprice": str(risk.trigger_price)}
            trade.sl_order_id = self.broker.place_order(sl_payload)
        else:
            trade.broker_order_id = f"PAPER-{trade.id}"
            trade.sl_order_id = f"PAPER-SL-{trade.id}"
        db.add(Position(trade_id=trade.id, symbol_id=symbol_id, quantity=quantity, avg_price=entry_price, ltp=entry_price))
        db.add(TradeLog(trade_id=trade.id, event_type="ENTRY", message=f"{mode} BUY {trading_symbol} qty={quantity}", payload={"stop_loss": stop_loss, "target": target}))
        db.commit()
        db.refresh(trade)
        return trade
