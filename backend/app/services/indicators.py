import pandas as pd

try:
    import talib
except Exception:  # pragma: no cover - optional binary package availability
    talib = None


def with_vwap(df: pd.DataFrame) -> pd.DataFrame:
    typical = (df["high"] + df["low"] + df["close"]) / 3
    vol = df["volume"].replace(0, 1)
    df["vwap"] = (typical * vol).cumsum() / vol.cumsum()
    return df


def cpr_from_previous_day(high: float, low: float, close: float) -> dict:
    pivot = (high + low + close) / 3
    bc = (high + low) / 2
    tc = (pivot - bc) + pivot
    return {"pivot": round(pivot, 2), "bc": round(min(bc, tc), 2), "tc": round(max(bc, tc), 2)}


def positive_momentum(df: pd.DataFrame, lookback: int = 3) -> bool:
    if len(df) < lookback:
        return False
    recent = df.tail(lookback)
    return bool((recent["close"].diff().dropna() > 0).all() and recent["close"].iloc[-1] > recent["open"].iloc[-1])


def talib_rsi(df: pd.DataFrame, period: int = 14) -> pd.Series:
    if talib is None:
        delta = df["close"].diff()
        gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
        rs = gain / loss.replace(0, pd.NA)
        return 100 - (100 / (1 + rs))
    return pd.Series(talib.RSI(df["close"].astype(float), timeperiod=period), index=df.index)


def manipulation_candle(df: pd.DataFrame, body_to_range_min: float = 0.15, wick_ratio_max: float = 3.0) -> bool:
    if df.empty:
        return True
    last = df.iloc[-1]
    candle_range = max(last["high"] - last["low"], 0.01)
    body = abs(last["close"] - last["open"])
    upper_wick = last["high"] - max(last["open"], last["close"])
    lower_wick = min(last["open"], last["close"]) - last["low"]
    return body / candle_range < body_to_range_min or max(upper_wick, lower_wick) / max(body, 0.01) > wick_ratio_max
