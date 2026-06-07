# Product Overview: Dhan Options Trading Platform

## 1. Product Purpose

This application is a full-stack options trading and research platform for Indian equity options using DhanHQ API v2.

The main objective is to scan Nifty 50 and Nifty Next 50 stocks, decide market/index sentiment from ATM option CPR behavior, filter strong moving stocks, select suitable options, store all scanner data, and prepare the framework for backtesting, paper trading, real trading, analytics, and future AI scoring.

The platform is designed as a practical trading desk, not a marketing site. The dashboard focuses on broker connection, scanner output, best candidates, all scanned options, daily PnL, storage health, risk state, and backtesting controls.

## 2. Current Technology Stack

Backend:

- Python FastAPI
- SQLAlchemy ORM
- PostgreSQL
- Redis
- Celery worker and beat
- Pandas and NumPy for backtesting and analytics
- DhanHQ API v2 adapter
- JWT/cookie based app access protection
- JSON logging

Frontend:

- React
- TypeScript
- Tailwind CSS
- Zustand state store
- Recharts
- TradingView widget panel

Infrastructure:

- Docker Compose
- Backend container
- Frontend container
- PostgreSQL container
- Redis container
- Celery worker container
- Celery beat container
- Environment variable configuration

## 3. Main Product Modules

### 3.1 Broker Authentication

The broker integration currently uses DhanHQ API v2.

Supported:

- Dhan Client ID login
- Dhan access token login
- PIN + TOTP based access token generation
- Encrypted broker session storage
- Broker status endpoint
- Profile and funds endpoints
- Token expiry display
- Session restore from stored database session or env token

Important limitation:

- True automatic Dhan token refresh is limited by Dhan's auth flow. The app can restore a valid token, but generating a fresh token still needs Dhan PIN/TOTP or a fresh access token.

### 3.2 Cloud Dashboard Protection

The app has a separate dashboard password gate.

Set this in `.env`:

```env
APP_ACCESS_PASSWORD=your-private-password
```

When this is set, the backend protects:

- `/api/v1/*`
- `/docs`
- `/openapi.json`
- `/redoc`

The frontend shows a private password screen before broker data or scanner data is visible.

If `APP_ACCESS_PASSWORD` is empty, the protection is disabled for local development.

### 3.3 Market Scanner

The scanner supports two separate universes:

- Nifty 50
- Nifty Next 50

The frontend has separate tabs for both.

The backend scanner is universe-aware through:

```json
{
  "universe": "NIFTY_50"
}
```

or:

```json
{
  "universe": "NIFTY_NEXT_50"
}
```

Nifty Next 50 symbols are fetched from the official Nifty Indices CSV with dummy symbols filtered out. If the official fetch fails, a local fallback list is used.

Known Dhan limitation:

- Some Nifty Next 50 stocks may not have Dhan stock option contracts. Currently `ENRIN`, `TATACAP`, and `TMCV` do not appear in Dhan option master and are marked neutral with reason `ATM stock option contract unavailable in Dhan instrument master`.

## 4. Exact Strategy Flow

The scanner follows this sequence:

1. Decide index sentiment.
2. Filter strong stocks.
3. Select proper ATM options.
4. Apply option filters.
5. Create final ranked option watchlist.

## 5. Sentiment Logic

For each stock in the selected universe:

1. Fetch equity quote.
2. Find nearest ATM CE and ATM PE stock options.
3. Fetch current premium for CE and PE.
4. Calculate CPR from previous trading day's option candle data.
5. Compare premium against CPR bottom line.

Stock sentiment rules:

- If ATM CE premium is above CE CPR bottom line, stock is bullish.
- If ATM PE premium is above PE CPR bottom line, stock is bearish.
- If neither condition is true, stock is neutral.
- If both CE and PE are above CPR bottom, the row is marked `BULLISH_AND_BEARISH`, and both counts can increase.

Final index sentiment:

- Bullish count greater than bearish count: `POSITIVE`
- Bearish count greater than bullish count: `NEGATIVE`
- Similar counts: `SIDEWAYS`

The scanner also calculates:

- Breadth score
- Sentiment score
- Confidence score
- Market regime

## 6. Stock Filtering Logic

After sentiment is decided:

1. Fetch live prices for all stocks in the selected universe.
2. Compare current price with previous close.
3. Calculate move percentage:

```text
((Current Price - Previous Close) / Previous Close) * 100
```

Strong stock rule:

- Select stock only if absolute move is at least 2%.

Bullish stock:

- Move is `>= +2%`

Bearish stock:

- Move is `<= -2%`

Stocks below 2% absolute move are ignored for option selection, but their sentiment data is still stored.

## 7. Option Selection Logic

For each strong stock:

1. Fetch ATM CE.
2. Fetch ATM PE.
3. Apply index sentiment rule.

If index sentiment is positive:

- CE and PE are allowed.
- Bullish stocks prefer CE.
- Bearish stocks prefer PE.

If index sentiment is negative:

- Only PE options are allowed.
- CE options are ignored.

If index sentiment is sideways:

- No trades are selected.

## 8. Option Filter Conditions

Selected options must satisfy all filters:

- High volume
- Tight spread
- Premium above minimum threshold
- Premium above CPR bottom line
- Premium above VWAP
- Strong momentum candles

Rejected options are still stored with rejection reasons.

Final watchlist ranking uses:

- Volume
- Momentum score
- Spread
- Underlying movement
- Final trade score

## 9. Dashboard Features

The current dashboard includes:

- Dhan connection status
- Dhan data plan status
- Nifty 50 scanner tab
- Nifty Next 50 scanner tab
- Daily PnL
- Realized PnL
- Unrealized PnL
- Breadth score
- Sentiment
- Trades today
- Perfect candidate panel
- All scanned options table
- Rejection reasons
- Backtest latest candidate controls
- Data storage health
- Risk state panel
- TradingView chart panel
- Recharts widgets

## 10. Data Storage

Current database tables include:

- `broker_sessions`
- `symbols`
- `historical_candles`
- `historical_data_cache`
- `option_chain`
- `daily_option_activity`
- `nifty_sentiment`
- `market_sentiment`
- `stock_sentiment`
- `option_watchlist`
- `scanned_option_snapshots`
- `filtered_stock_snapshots`
- `strategy_signals`
- `trades`
- `positions`
- `trade_logs`

Scanner storage:

- Every stock sentiment row is stored.
- Filter lifecycle rows are stored for strong stocks entering, staying active, or exiting the filter.
- Every selected/scanned option is stored.
- Final watchlist rows are stored separately.

## 11. Backtesting

The backtesting engine supports:

- Historical Dhan intraday candles
- Latest scanner candidate backtest
- Historical data cache
- Opening range from 9:15 to 9:25
- 5-minute breakout entry
- VWAP hold
- Volume confirmation
- Risk-based position sizing
- Stop loss
- Target
- VWAP exit
- Time-based square-off
- Max 2 trades per day
- Slippage and brokerage assumptions

Backtest metrics include:

- Trades
- Win rate
- Profit factor
- Expectancy
- Max drawdown
- Sharpe ratio
- Equity curve

## 12. Paper and Live Trading

Paper trading:

- Uses the same execution object as live trading.
- Creates paper broker order IDs.
- Stores trades and positions.

Live trading:

- Disabled by default.
- Requires:

```env
LIVE_TRADING_ENABLED=true
```

Live order behavior:

1. Place Dhan market buy order.
2. Immediately place Dhan stop-loss sell order.
3. Store entry order ID and SL order ID.
4. Use idempotency key to reduce duplicate trade risk.

Stop-loss order payload uses:

- `orderType: STOP_LOSS`
- `triggerPrice`
- `price` as SL limit price

## 13. Risk Management

Current risk controls:

- Maximum trades per day defaults to 2 in strategy config.
- Risk per trade defaults to Rs 6,000 in dashboard backtest config.
- Max daily loss default is Rs 12,000.
- Live trading disabled by default.
- Duplicate trade prevention through idempotency keys.
- Stop-loss order created immediately after live entry.

Planned improvements:

- Stronger live kill switch
- Consecutive loss blocker
- Emergency square-off
- Trading window enforcement for manual orders
- Better position-level risk dashboard

## 14. Celery Scheduler

Current scheduled tasks:

- `live_market_scan`
- `pre_market_data_sync`
- `end_of_day_analytics`

Important update:

- `live_market_scan` now skips outside market session.
- It does not run on weekends.
- This avoids unnecessary Dhan requests and rate-limit errors on non-market days.

Current schedule still sends the task every minute, but the task exits immediately outside market hours.

## 15. Alerts

Telegram alert support exists but is disabled unless configured.

Set:

```env
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Implemented alert points:

- Trade entry
- Trade exit reconciliation
- Scanner candidate from scheduled scan

## 16. WebSocket Status

Implemented:

- Application dashboard WebSocket endpoint:

```text
/api/v1/ws/dashboard
```

It streams dashboard analytics snapshots.

Not fully implemented:

- Raw Dhan market tick WebSocket subscription.
- Tick-to-candle aggregation.
- Live market depth streaming.

## 17. What Is Working Now

Working:

- Docker stack
- FastAPI backend
- React frontend
- Dhan login/session restore
- Dhan profile/status/data plan check
- Nifty 50 scanner
- Nifty Next 50 scanner
- CPR-based sentiment engine
- Option filter pipeline
- Data storage
- Daily analytics endpoint
- Backtest endpoint
- Historical data cache
- App password gate
- Celery task registration
- Celery market-session guard
- Telegram alert scaffolding
- Trade reconciliation scaffolding

Partially working:

- Daily PnL, because it depends on actual trades/positions.
- Unrealized PnL, because it needs open positions.
- Trade auto-exit reconciliation, because it needs real Dhan order status to verify.
- Scheduled scanner, because it works but should later be made more configurable.
- WebSocket, because app dashboard streaming exists but raw Dhan feed is not complete.

Not fully implemented:

- Raw Dhan WebSocket market feed.
- Full production-grade broker postback handling.
- Full AI scoring model.
- Full strategy optimization engine.
- Full multi-broker support.
- Full exchange holiday calendar.
- Alembic migrations.

## 18. Current Known Notes

As of Sunday, June 7, 2026:

- Market is closed.
- Live stock move percentages can come as `0.0`.
- Strong stock count can be zero.
- Final watchlist can be zero.
- This is expected outside live market hours.

Nifty Next 50 latest verification:

```text
Scanned symbols: 50
Stock sentiment rows: 50
Unavailable option contracts: 3
Unavailable: ENRIN, TATACAP, TMCV
```

## 19. How To Run

Create `.env`:

```bash
copy .env.example .env
```

Start:

```bash
docker compose up -d --build
```

Open:

```text
Frontend: http://localhost:5173
Backend docs: http://localhost:8000/docs
```

Check backend:

```text
http://localhost:8000/health
```

## 20. Production Deployment Notes

For AWS/cloud deployment:

Set a private app password:

```env
APP_ACCESS_PASSWORD=your-private-password
```

Use strong secrets:

```env
JWT_SECRET=long-random-secret
CREDENTIAL_KEY=valid-fernet-key
```

Keep live trading disabled until fully verified:

```env
LIVE_TRADING_ENABLED=false
```

Recommended next production steps:

- Add HTTPS.
- Restrict inbound ports.
- Add Alembic migrations.
- Add backup policy for PostgreSQL.
- Add structured monitoring.
- Add broker postback endpoint.
- Add exchange holiday calendar.
- Add Dhan WebSocket feed.
- Add scan locking during market hours.

## 21. Product Roadmap

Near-term:

1. Add scan lock to prevent overlapping market-hour scans.
2. Add UI display for unavailable option contracts.
3. Add stronger analytics page for stored scanner history.
4. Add raw Dhan WebSocket feed.
5. Add order status reconciliation dashboard.
6. Add daily/weekly/monthly reports.

Medium-term:

1. Add AI feature collection dashboard.
2. Add smart money scoring reports.
3. Add sector-wise breadth.
4. Add BankNifty alignment.
5. Add market regime analytics.
6. Add strategy optimizer.

Long-term:

1. AI scoring model.
2. Multi-strategy engine.
3. Multi-broker support.
4. Full trade replay system.
5. Production deployment automation.

