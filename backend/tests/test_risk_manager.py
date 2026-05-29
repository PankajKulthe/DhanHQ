from app.risk.manager import RiskManager
from app.schemas.trading import StrategyConfig


def test_position_size_uses_allowed_risk_and_lot_size():
    config = StrategyConfig(risk_per_trade=6000)
    decision = RiskManager().evaluate_entry(entry=120, stop_loss=114, lot_size=50, daily_pnl=0, open_exposure=0, trade_count=0, config=config)
    assert decision.allowed
    assert decision.quantity == 1000
    assert decision.trigger_price == 114
