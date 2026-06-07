from datetime import datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.session import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class BrokerSession(Base, TimestampMixin):
    __tablename__ = "broker_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    broker: Mapped[str] = mapped_column(String(32), default="DHAN")
    client_code: Mapped[str] = mapped_column(String(64), index=True)
    jwt_token_enc: Mapped[str] = mapped_column(Text)
    refresh_token_enc: Mapped[str] = mapped_column(Text)
    feed_token_enc: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)


class Symbol(Base, TimestampMixin):
    __tablename__ = "symbols"
    id: Mapped[int] = mapped_column(primary_key=True)
    exchange: Mapped[str] = mapped_column(String(16), index=True)
    token: Mapped[str] = mapped_column(String(32), index=True)
    trading_symbol: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    instrument_type: Mapped[str | None] = mapped_column(String(32))
    expiry: Mapped[Date | None] = mapped_column(Date)
    strike: Mapped[float | None] = mapped_column(Float)
    lot_size: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("exchange", "token", name="uq_symbols_exchange_token"),)


class HistoricalCandle(Base):
    __tablename__ = "historical_candles"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    timeframe: Mapped[str] = mapped_column(String(16), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    oi: Mapped[int | None] = mapped_column(Integer)
    symbol: Mapped[Symbol] = relationship()
    __table_args__ = (UniqueConstraint("symbol_id", "timeframe", "ts", name="uq_candle_symbol_tf_ts"),)


class HistoricalDataCache(Base):
    __tablename__ = "historical_data_cache"
    id: Mapped[int] = mapped_column(primary_key=True)
    broker: Mapped[str] = mapped_column(String(32), default="DHAN", index=True)
    security_id: Mapped[str] = mapped_column(String(32), index=True)
    exchange_segment: Mapped[str] = mapped_column(String(32), index=True)
    instrument: Mapped[str] = mapped_column(String(32), index=True)
    interval: Mapped[str] = mapped_column(String(16), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    oi: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "broker",
            "security_id",
            "exchange_segment",
            "instrument",
            "interval",
            "ts",
            name="uq_dhan_hist_cache_key",
        ),
    )


class OptionChain(Base, TimestampMixin):
    __tablename__ = "option_chain"
    id: Mapped[int] = mapped_column(primary_key=True)
    underlying: Mapped[str] = mapped_column(String(64), index=True)
    expiry: Mapped[Date] = mapped_column(Date, index=True)
    strike: Mapped[float] = mapped_column(Float, index=True)
    ce_symbol_id: Mapped[int | None] = mapped_column(ForeignKey("symbols.id"))
    pe_symbol_id: Mapped[int | None] = mapped_column(ForeignKey("symbols.id"))
    ce_ltp: Mapped[float | None] = mapped_column(Float)
    pe_ltp: Mapped[float | None] = mapped_column(Float)
    ce_volume: Mapped[int | None] = mapped_column(Integer)
    pe_volume: Mapped[int | None] = mapped_column(Integer)
    ce_oi: Mapped[int | None] = mapped_column(Integer)
    pe_oi: Mapped[int | None] = mapped_column(Integer)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class DailyOptionActivity(Base, TimestampMixin):
    __tablename__ = "daily_option_activity"
    id: Mapped[int] = mapped_column(primary_key=True)
    trade_date: Mapped[Date] = mapped_column(Date, index=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    underlying_move_pct: Mapped[float] = mapped_column(Float)
    premium: Mapped[float] = mapped_column(Float)
    volume: Mapped[int] = mapped_column(Integer)
    oi: Mapped[int | None] = mapped_column(Integer)
    vwap: Mapped[float | None] = mapped_column(Float)
    cpr_pivot: Mapped[float | None] = mapped_column(Float)
    score: Mapped[float] = mapped_column(Float, default=0)
    tags: Mapped[dict] = mapped_column(JSON, default=dict)


class NiftySentiment(Base, TimestampMixin):
    __tablename__ = "nifty_sentiment"
    id: Mapped[int] = mapped_column(primary_key=True)
    trade_date: Mapped[Date] = mapped_column(Date, index=True)
    breadth_score: Mapped[int] = mapped_column(Integer)
    bullish_count: Mapped[int] = mapped_column(Integer)
    bearish_count: Mapped[int] = mapped_column(Integer)
    neutral_count: Mapped[int] = mapped_column(Integer)
    sentiment: Mapped[str] = mapped_column(String(16), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class MarketSentiment(Base):
    __tablename__ = "market_sentiment"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    bullish_count: Mapped[int] = mapped_column(Integer, default=0)
    bearish_count: Mapped[int] = mapped_column(Integer, default=0)
    neutral_count: Mapped[int] = mapped_column(Integer, default=0)
    final_sentiment: Mapped[str] = mapped_column(String(16), index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class StockSentimentSnapshot(Base):
    __tablename__ = "stock_sentiment"
    id: Mapped[int] = mapped_column(primary_key=True)
    stock_symbol: Mapped[str] = mapped_column(String(64), index=True)
    stock_move_percent: Mapped[float] = mapped_column(Float, default=0)
    ce_price: Mapped[float] = mapped_column(Float, default=0)
    pe_price: Mapped[float] = mapped_column(Float, default=0)
    ce_cpr_bottom: Mapped[float] = mapped_column(Float, default=0)
    pe_cpr_bottom: Mapped[float] = mapped_column(Float, default=0)
    stock_sentiment: Mapped[str] = mapped_column(String(32), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class OptionWatchlistSnapshot(Base):
    __tablename__ = "option_watchlist"
    id: Mapped[int] = mapped_column(primary_key=True)
    stock_symbol: Mapped[str] = mapped_column(String(64), index=True)
    option_symbol: Mapped[str] = mapped_column(String(128), index=True)
    option_type: Mapped[str] = mapped_column(String(8), index=True)
    premium: Mapped[float] = mapped_column(Float, default=0)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    spread: Mapped[float | None] = mapped_column(Float)
    vwap: Mapped[float | None] = mapped_column(Float)
    cpr_status: Mapped[str] = mapped_column(String(32), index=True)
    momentum_score: Mapped[float] = mapped_column(Float, default=0)
    final_rank: Mapped[int | None] = mapped_column(Integer)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class ScannedOptionSnapshot(Base):
    __tablename__ = "scanned_option_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    stock_symbol: Mapped[str] = mapped_column(String(64), index=True)
    option_symbol: Mapped[str] = mapped_column(String(128), index=True)
    option_type: Mapped[str] = mapped_column(String(8), index=True)
    premium: Mapped[float] = mapped_column(Float, default=0)
    volume: Mapped[int] = mapped_column(Integer, default=0)
    spread: Mapped[float | None] = mapped_column(Float)
    vwap: Mapped[float | None] = mapped_column(Float)
    cpr_status: Mapped[str] = mapped_column(String(32), index=True)
    momentum_score: Mapped[float] = mapped_column(Float, default=0)
    smart_money_score: Mapped[float] = mapped_column(Float, default=0)
    final_trade_score: Mapped[float] = mapped_column(Float, default=0)
    eligible: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class FilteredStockSnapshot(Base):
    __tablename__ = "filtered_stock_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    stock_symbol: Mapped[str] = mapped_column(String(64), index=True)
    stock_move_percent: Mapped[float] = mapped_column(Float, default=0)
    stock_bias: Mapped[str] = mapped_column(String(16), index=True)
    event: Mapped[str] = mapped_column(String(32), index=True)
    entered_at: Mapped[datetime | None] = mapped_column(DateTime)
    exited_at: Mapped[datetime | None] = mapped_column(DateTime)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class StrategySignal(Base, TimestampMixin):
    __tablename__ = "strategy_signals"
    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_name: Mapped[str] = mapped_column(String(64), index=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    direction: Mapped[str] = mapped_column(String(8))
    signal_time: Mapped[datetime] = mapped_column(DateTime, index=True)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    target: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="NEW")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)


class Trade(Base, TimestampMixin):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(primary_key=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    mode: Mapped[str] = mapped_column(String(16), default="PAPER")
    strategy_name: Mapped[str] = mapped_column(String(64), index=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    side: Mapped[str] = mapped_column(String(8))
    quantity: Mapped[int] = mapped_column(Integer)
    entry_price: Mapped[float] = mapped_column(Float)
    stop_loss: Mapped[float] = mapped_column(Float)
    target: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(32), default="OPEN", index=True)
    broker_order_id: Mapped[str | None] = mapped_column(String(64))
    sl_order_id: Mapped[str | None] = mapped_column(String(64))
    exit_price: Mapped[float | None] = mapped_column(Float)
    realized_pnl: Mapped[float] = mapped_column(Float, default=0)
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime)


class Position(Base, TimestampMixin):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(primary_key=True)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id"), index=True)
    symbol_id: Mapped[int] = mapped_column(ForeignKey("symbols.id"), index=True)
    quantity: Mapped[int] = mapped_column(Integer)
    avg_price: Mapped[float] = mapped_column(Float)
    ltp: Mapped[float] = mapped_column(Float, default=0)
    unrealized_pnl: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(32), default="OPEN")


class TradeLog(Base):
    __tablename__ = "trade_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    trade_id: Mapped[int | None] = mapped_column(ForeignKey("trades.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


Index("ix_candle_symbol_tf_time", HistoricalCandle.symbol_id, HistoricalCandle.timeframe, HistoricalCandle.ts)
