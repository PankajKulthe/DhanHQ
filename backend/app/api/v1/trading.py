from datetime import date, datetime, time
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import Symbol, Trade
from app.risk.manager import RiskManager
from app.schemas.trading import OrderRequest, StrategyConfig
from app.services.auth_service import broker_auth_service
from app.services.execution import ExecutionEngine

router = APIRouter(prefix="/trading", tags=["trading"])


@router.post("/orders")
def place_order(payload: OrderRequest, db: Session = Depends(get_db)) -> dict:
    symbol = db.get(Symbol, payload.symbol_id)
    if not symbol:
        raise HTTPException(status_code=404, detail="Symbol not found")
    start = datetime.combine(date.today(), time.min)
    end = datetime.combine(date.today(), time.max)
    todays_trades = db.query(Trade).filter(Trade.opened_at >= start, Trade.opened_at <= end).all()
    daily_pnl = sum(float(trade.realized_pnl or 0) for trade in todays_trades)
    open_exposure = sum(float(trade.entry_price or 0) * int(trade.quantity or 0) for trade in todays_trades if trade.status == "OPEN")
    config = StrategyConfig(max_trades_per_day=2)
    entry_price = payload.price or 0
    stop_loss = payload.trigger_price or 0
    if entry_price <= 0 or stop_loss <= 0:
        raise HTTPException(status_code=400, detail="price and trigger_price are required for protected order sizing")
    risk = RiskManager().evaluate_entry(
        entry=entry_price,
        stop_loss=stop_loss,
        lot_size=symbol.lot_size,
        daily_pnl=daily_pnl,
        open_exposure=open_exposure,
        trade_count=len(todays_trades),
        config=config,
    )
    if not risk.allowed:
        raise HTTPException(status_code=400, detail=risk.reason)
    trade = ExecutionEngine(broker_auth_service.broker).place_market_buy_with_sl(
        db,
        symbol_id=symbol.id,
        trading_symbol=symbol.trading_symbol,
        token=symbol.token,
        quantity=risk.quantity or payload.quantity,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target=None,
        strategy_name="MANUAL",
        mode=payload.mode,
        idempotency_key=payload.idempotency_key,
        risk=risk,
    )
    return {"trade_id": trade.id, "status": trade.status, "broker_order_id": trade.broker_order_id, "sl_order_id": trade.sl_order_id}
