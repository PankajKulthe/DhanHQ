from dataclasses import dataclass
import pandas as pd
from app.backtesting.metrics import performance_metrics
from app.schemas.trading import BacktestRequest


@dataclass
class SimulatedFill:
    entry_time: str
    exit_time: str
    entry: float
    exit: float
    quantity: int
    pnl: float
    reason: str


class BacktestingEngine:
    def run_breakout_backtest(self, candles: pd.DataFrame, request: BacktestRequest, lot_size: int = 50) -> dict:
        config = request.config
        fills: list[SimulatedFill] = []
        if candles.empty:
            return {"metrics": performance_metrics(pd.DataFrame(), config.capital), "trades": []}
        candles = candles.sort_values("ts").copy()
        for day, day_df in candles.groupby(candles["ts"].dt.date):
            range_df = day_df[(day_df["ts"].dt.strftime("%H:%M") >= config.range_start) & (day_df["ts"].dt.strftime("%H:%M") <= config.range_end)]
            if range_df.empty:
                continue
            high, low = range_df["high"].max(), range_df["low"].min()
            open_trade = None
            for row in day_df[day_df["ts"].dt.strftime("%H:%M") > config.range_end].itertuples():
                if open_trade is None and row.close > high:
                    entry = row.close * (1 + request.slippage_bps / 10000)
                    stop = low if config.sl_mode == "CANDLE" else entry * 0.95
                    qty = int(config.risk_per_trade / max(entry - stop, 0.01)) // lot_size * lot_size
                    if qty <= 0:
                        continue
                    open_trade = {"entry": entry, "stop": stop, "target": entry + (entry - stop) * config.rr, "qty": qty, "entry_time": str(row.ts)}
                elif open_trade:
                    exit_price = reason = None
                    if row.low <= open_trade["stop"]:
                        exit_price, reason = open_trade["stop"], "SL"
                    elif row.high >= open_trade["target"]:
                        exit_price, reason = open_trade["target"], "TARGET"
                    elif str(row.ts)[11:16] >= config.square_off_time:
                        exit_price, reason = row.close, "TIME"
                    if exit_price:
                        exit_price *= 1 - request.slippage_bps / 10000
                        pnl = (exit_price - open_trade["entry"]) * open_trade["qty"] - (request.brokerage_per_order * 2)
                        fills.append(SimulatedFill(open_trade["entry_time"], str(row.ts), open_trade["entry"], exit_price, open_trade["qty"], pnl, reason))
                        open_trade = None
                        break
        trades = pd.DataFrame([f.__dict__ for f in fills])
        return {"metrics": performance_metrics(trades, config.capital), "trades": [f.__dict__ for f in fills]}
