from datetime import time
import pandas as pd
from app.schemas.trading import StrategyConfig


class BreakoutStrategyEngine:
    name = "OPENING_RANGE_OPTION_BREAKOUT"

    def opening_range(self, candles: pd.DataFrame, config: StrategyConfig) -> dict | None:
        start_h, start_m = [int(x) for x in config.range_start.split(":")]
        end_h, end_m = [int(x) for x in config.range_end.split(":")]
        session = candles[(candles["ts"].dt.time >= time(start_h, start_m)) & (candles["ts"].dt.time <= time(end_h, end_m))]
        if session.empty:
            return None
        return {"high": float(session["high"].max()), "low": float(session["low"].min())}

    def signal(self, option: dict, candles_5m: pd.DataFrame, market_sentiment: str, config: StrategyConfig) -> dict | None:
        rng = self.opening_range(candles_5m, config)
        if not rng or candles_5m.empty:
            return None
        last = candles_5m.iloc[-1]
        aligned = (market_sentiment == "BULLISH" and option.get("type") == "CE") or (market_sentiment == "BEARISH" and option.get("type") == "PE")
        if (
            last["close"] > rng["high"]
            and option.get("volume_confirmed", False)
            and option.get("positive_momentum", False)
            and option.get("premium", 0) > option.get("vwap", 0)
            and option.get("premium", 0) > option.get("cpr_tc", 0)
            and aligned
        ):
            entry = float(last["close"])
            stop = float(rng["low"] if config.sl_mode == "CANDLE" else entry * 0.95)
            return {"strategy_name": self.name, "side": "BUY", "entry_price": entry, "stop_loss": stop, "target": entry + ((entry - stop) * config.rr), "range": rng}
        return None
