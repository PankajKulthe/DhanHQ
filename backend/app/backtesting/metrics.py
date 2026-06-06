import numpy as np
import pandas as pd


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    dd = (equity - peak) / peak.replace(0, np.nan)
    return float(dd.min() or 0)


def performance_metrics(trades: pd.DataFrame, starting_capital: float) -> dict:
    if trades.empty:
        return {"trades": 0, "win_rate": 0, "profit_factor": 0, "max_drawdown": 0, "expectancy": 0}
    pnl = trades["pnl"].astype(float)
    wins = pnl[pnl > 0]
    losses = pnl[pnl < 0]
    equity = starting_capital + pnl.cumsum()
    profit_factor = float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 0 else float("inf")
    returns = equity.pct_change().fillna(0)
    sharpe_raw = float((returns.mean() / returns.std()) * np.sqrt(252)) if returns.std() else 0
    sharpe = sharpe_raw if np.isfinite(sharpe_raw) else 0
    months = trades.assign(month=pd.to_datetime(trades["exit_time"]).dt.to_period("M")).groupby("month")["pnl"].sum().astype(float).to_dict()
    return {
        "trades": int(len(trades)),
        "win_rate": round(float((pnl > 0).mean() * 100), 2),
        "profit_factor": round(profit_factor, 2) if np.isfinite(profit_factor) else 999,
        "max_drawdown": round(max_drawdown(equity), 4),
        "sharpe_ratio": round(sharpe, 2),
        "expectancy": round(float(pnl.mean()), 2),
        "consecutive_wins": _max_streak(pnl > 0),
        "consecutive_losses": _max_streak(pnl < 0),
        "monthly_performance": {str(k): round(v, 2) for k, v in months.items()},
        "equity_curve": [round(x, 2) for x in equity.tolist()],
    }


def _max_streak(mask: pd.Series) -> int:
    best = cur = 0
    for value in mask.tolist():
        cur = cur + 1 if value else 0
        best = max(best, cur)
    return best
