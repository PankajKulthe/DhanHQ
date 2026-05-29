from datetime import date, datetime
from pydantic import BaseModel, Field


class BrokerLoginRequest(BaseModel):
    api_key: str
    client_code: str
    password: str
    totp: str | None = None
    totp_secret: str | None = None


class BrokerStatus(BaseModel):
    broker: str = "ANGEL_ONE"
    connected: bool
    client_code: str | None = None
    feed_connected: bool = False
    message: str = ""


class StrategyConfig(BaseModel):
    mode: str = Field(default="PAPER", pattern="^(PAPER|LIVE)$")
    capital: float = 500000
    risk_per_trade: float = 6000
    max_daily_loss: float = 12000
    max_trades_per_day: int = 6
    min_underlying_move_pct: float = 2
    min_premium: float = 20
    min_volume: int = 50000
    max_spread_pct: float = 2.5
    positive_breadth_threshold: int = 8
    negative_breadth_threshold: int = -8
    range_start: str = "09:15"
    range_end: str = "09:25"
    square_off_time: str = "15:15"
    sl_mode: str = "RISK"
    target_mode: str = "FIXED_RR"
    rr: float = 2.0


class BacktestRequest(BaseModel):
    from_date: date
    to_date: date
    symbol_ids: list[int] = []
    config: StrategyConfig = Field(default_factory=StrategyConfig)
    slippage_bps: float = 5
    brokerage_per_order: float = 20
    fill_delay_seconds: int = 2


class OrderRequest(BaseModel):
    symbol_id: int
    side: str = Field(pattern="^(BUY|SELL)$")
    quantity: int
    order_type: str = "MARKET"
    price: float | None = None
    trigger_price: float | None = None
    mode: str = Field(default="PAPER", pattern="^(PAPER|LIVE)$")
    idempotency_key: str


class ScanResult(BaseModel):
    generated_at: datetime
    sentiment: str
    breadth_score: int
    candidates: list[dict]
