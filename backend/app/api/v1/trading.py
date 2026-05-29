from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import Symbol
from app.risk.manager import RiskDecision
from app.schemas.trading import OrderRequest
from app.services.auth_service import broker_auth_service
from app.services.execution import ExecutionEngine

router = APIRouter(prefix="/trading", tags=["trading"])


@router.post("/orders")
def place_order(payload: OrderRequest, db: Session = Depends(get_db)) -> dict:
    symbol = db.get(Symbol, payload.symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol not found")
    risk = RiskDecision(True, quantity=payload.quantity, trigger_price=payload.trigger_price or 0, sl_limit_price=payload.price or 0)
    trade = ExecutionEngine(broker_auth_service.broker).place_market_buy_with_sl(
        db,
        symbol_id=symbol.id,
        trading_symbol=symbol.trading_symbol,
        token=symbol.token,
        quantity=payload.quantity,
        entry_price=payload.price or 0,
        stop_loss=payload.trigger_price or 0,
        target=None,
        strategy_name="MANUAL",
        mode=payload.mode,
        idempotency_key=payload.idempotency_key,
        risk=risk,
    )
    return {"trade_id": trade.id, "status": trade.status, "broker_order_id": trade.broker_order_id, "sl_order_id": trade.sl_order_id}
