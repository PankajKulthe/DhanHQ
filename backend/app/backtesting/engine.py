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
            return {"metrics": performance_metrics(pd.DataFrame(), config.capital), "trades": [], "rules": self.rules(config)}
        candles = candles.sort_values("ts").copy()
        candles["vwap"] = self._vwap(candles)
        for day, day_df in candles.groupby(candles["ts"].dt.date):
            trades_for_day = 0
            range_df = day_df[(day_df["ts"].dt.strftime("%H:%M") >= config.range_start) & (day_df["ts"].dt.strftime("%H:%M") <= config.range_end)]
            if range_df.empty:
                continue
            high, low = range_df["high"].max(), range_df["low"].min()
            open_trade = None
            for row in day_df[day_df["ts"].dt.strftime("%H:%M") > config.range_end].itertuples():
                previous = day_df[day_df["ts"] < row.ts].tail(3)
                avg_volume = previous["volume"].mean() if not previous.empty else 0
                volume_ok = row.volume >= avg_volume * config.volume_confirmation_multiplier if avg_volume > 0 else True
                vwap_ok = row.close > row.vwap if row.vwap > 0 else True
                breakout_ok = row.close > high and volume_ok and vwap_ok
                if open_trade is None and trades_for_day < config.max_trades_per_day and breakout_ok:
                    entry = row.close * (1 + request.slippage_bps / 10000)
                    stop = self._stop_loss(entry=entry, range_low=low, candle_low=row.low, config=config)
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
                    elif config.vwap_exit_enabled and row.vwap > 0 and row.close < row.vwap:
                        exit_price, reason = row.close, "VWAP_EXIT"
                    elif str(row.ts)[11:16] >= config.square_off_time:
                        exit_price, reason = row.close, "TIME"
                    if exit_price:
                        exit_price *= 1 - request.slippage_bps / 10000
                        pnl = (exit_price - open_trade["entry"]) * open_trade["qty"] - (request.brokerage_per_order * 2)
                        fills.append(SimulatedFill(open_trade["entry_time"], str(row.ts), open_trade["entry"], exit_price, open_trade["qty"], pnl, reason))
                        open_trade = None
                        trades_for_day += 1
                        if trades_for_day >= config.max_trades_per_day:
                            break
        trades = pd.DataFrame([f.__dict__ for f in fills])
        return {"metrics": performance_metrics(trades, config.capital), "trades": [f.__dict__ for f in fills], "rules": self.rules(config)}

    @staticmethod
    def _vwap(candles: pd.DataFrame) -> pd.Series:
        typical = (candles["high"].astype(float) + candles["low"].astype(float) + candles["close"].astype(float)) / 3
        volume = candles["volume"].astype(float).clip(lower=0)
        cumulative_volume = volume.cumsum().replace(0, pd.NA)
        return (typical * volume).cumsum() / cumulative_volume

    @staticmethod
    def _stop_loss(*, entry: float, range_low: float, candle_low: float, config) -> float:
        percent_sl = entry * 0.92
        candle_sl = float(candle_low or 0)
        range_sl = float(range_low or 0)
        if config.sl_mode == "CANDLE":
            stop = candle_sl
        elif config.sl_mode == "PERCENT":
            stop = percent_sl
        else:
            stop = max(value for value in [range_sl, candle_sl, percent_sl] if value > 0)
        if stop >= entry:
            stop = entry * 0.92
        return round(stop, 2)

    @staticmethod
    def rules(config) -> dict:
        return {
            "range": f"{config.range_start}-{config.range_end}",
            "entry": "5-minute option candle closes above opening range high with volume confirmation and VWAP hold",
            "stop_loss": "risk mode uses tighter of range low, breakout candle low, and 8 percent premium SL; SL limit is below trigger for sell order",
            "target": f"fixed {config.rr}:1 reward-risk target",
            "exits": ["stop_loss", "target", "vwap_exit", f"time_square_off_{config.square_off_time}"],
            "max_trades_per_day": config.max_trades_per_day,
        }
