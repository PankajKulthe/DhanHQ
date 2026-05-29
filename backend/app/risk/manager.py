from dataclasses import dataclass
from app.schemas.trading import StrategyConfig


@dataclass
class RiskDecision:
    allowed: bool
    reason: str = ""
    quantity: int = 0
    trigger_price: float = 0
    sl_limit_price: float = 0


class RiskManager:
    def evaluate_entry(self, entry: float, stop_loss: float, lot_size: int, daily_pnl: float, open_exposure: float, trade_count: int, config: StrategyConfig, kill_switch: bool = False) -> RiskDecision:
        if kill_switch:
            return RiskDecision(False, "kill_switch_enabled")
        if daily_pnl <= -abs(config.max_daily_loss):
            return RiskDecision(False, "max_daily_loss_reached")
        if trade_count >= config.max_trades_per_day:
            return RiskDecision(False, "max_trades_reached")
        if open_exposure >= config.capital * 0.35:
            return RiskDecision(False, "max_capital_exposure_reached")
        risk_per_unit = max(entry - stop_loss, 0)
        if risk_per_unit <= 0:
            return RiskDecision(False, "invalid_stop_loss")
        raw_qty = int(config.risk_per_trade / risk_per_unit)
        lots = max(raw_qty // lot_size, 0)
        quantity = lots * lot_size
        if quantity <= 0:
            return RiskDecision(False, "risk_too_small_for_lot_size")
        return RiskDecision(True, quantity=quantity, trigger_price=round(stop_loss, 2), sl_limit_price=round(stop_loss * 0.995, 2))
