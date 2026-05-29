from fastapi import APIRouter
from app.schemas.trading import BacktestRequest

router = APIRouter(prefix="/backtests", tags=["backtests"])


@router.post("/run")
def run_backtest(payload: BacktestRequest) -> dict:
    import pandas as pd
    from app.backtesting.engine import BacktestingEngine

    candles = pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume"])
    return BacktestingEngine().run_breakout_backtest(candles, payload)
