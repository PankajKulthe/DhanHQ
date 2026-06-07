from datetime import date, datetime
from pydantic import BaseModel, Field


class BrokerLoginRequest(BaseModel):
    client_id: str | None = None
    dhan_client_id: str | None = None
    client_code: str | None = None
    access_token: str | None = None
    accessToken: str | None = None
    pin: str | None = None
    password: str | None = None
    totp: str | None = None
    totp_secret: str | None = None


class BrokerStatus(BaseModel):
    broker: str = "DHAN"
    connected: bool
    client_code: str | None = None
    feed_connected: bool = False
    message: str = ""
    active_segment: str | None = None
    data_plan: str | None = None
    data_validity: str | None = None
    token_expires_at: datetime | None = None


class StrategyConfig(BaseModel):
    universe: str = Field(default="NIFTY_50", pattern="^(NIFTY_50|NIFTY_NEXT_50)$")
    mode: str = Field(default="PAPER", pattern="^(PAPER|LIVE)$")
    capital: float = 500000
    risk_per_trade: float = 6000
    max_daily_loss: float = 12000
    max_trades_per_day: int = 2
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
    volume_confirmation_multiplier: float = 1.2
    vwap_exit_enabled: bool = True
    min_trade_score: float = 75


class BacktestRequest(BaseModel):
    from_date: date
    to_date: date
    security_id: str | None = None
    option_symbol: str | None = None
    exchange_segment: str = "NSE_FNO"
    instrument: str = "OPTSTK"
    interval: str = "5"
    lot_size: int = 1
    use_latest_candidate: bool = True
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
    universe: str = "NIFTY_50"
    index_name: str = "Nifty 50"
    sentiment: str
    breadth_score: int
    nifty_sentiment: str | None = None
    bullish_count: int = 0
    bearish_count: int = 0
    neutral_count: int = 0
    scanned_symbols: int = 0
    moved_count: int = 0
    sentiment_score: float | None = None
    confidence_score: float | None = None
    market_regime: str | None = None
    bullish_stock_list: list[str] = Field(default_factory=list)
    bearish_stock_list: list[str] = Field(default_factory=list)
    stock_sentiments: list[dict] = Field(default_factory=list)
    top_gainers: list[dict] = Field(default_factory=list)
    top_losers: list[dict] = Field(default_factory=list)
    strong_stocks: list[dict] = Field(default_factory=list)
    selected_atm_options: list[dict] = Field(default_factory=list)
    final_option_watchlist: list[dict] = Field(default_factory=list)
    candidates: list[dict] = Field(default_factory=list)
    low_confidence: bool = False
    no_trade_reason: str = ""
