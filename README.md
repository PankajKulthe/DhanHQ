# Angel Options Trading Platform

Production-oriented full-stack scaffold for Indian options trading on Angel One SmartAPI.

## What Is Included

- FastAPI backend with SQLAlchemy models for symbols, candles, option chain, daily activity, Nifty sentiment, strategy signals, trades, positions, and trade logs.
- Angel One SmartAPI adapter for session generation, token refresh, WebSocket boundary, market data, and order placement.
- Nifty 50 filtering, breadth sentiment, option eligibility checks, opening-range breakout strategy, risk sizing, paper/live execution boundary, backtesting metrics, and daily analytics.
- React + TypeScript dashboard with broker connection, market scan, risk state, TradingView chart, and Recharts widgets.
- PostgreSQL, Redis, Celery worker/beat, Docker Compose, environment-driven configuration, and JSON logging.

## Safety Defaults

Live trading is disabled unless `LIVE_TRADING_ENABLED=true` is set. The execution layer also requires an idempotency key per trade to prevent duplicate orders. Use paper mode until SmartAPI credentials, symbols, lot sizes, and order payloads have been verified against your Angel One account.

## Quick Start

```bash
copy .env.example .env
docker compose up --build
```

Open:

- Backend: http://localhost:8000/docs
- Frontend: http://localhost:5173

## SmartAPI Notes

The current public docs identify `loginByPassword`, `generateTokens`, historical candle endpoint, WebSocket 2.0 at `wss://smartapisocket.angelone.in/smart-stream`, 30 second ping/pong heartbeats, and cumulative order rate limits around 9 requests per second. Those constraints are isolated in `backend/app/brokers/smartapi.py` and the execution layer.

## Next Hardening Steps

1. Add Alembic migrations before production deployment.
2. Load and normalize Angel One scrip master into `symbols`.
3. Wire Celery tasks to real market data collection windows.
4. Add exchange holiday calendar and expiry rollover rules.
5. Add broker postback endpoint for order status reconciliation.
6. Add full WebSocket subscription management and tick-to-candle aggregation.
7. Expand tests around duplicate order prevention, SL placement failures, and daily kill switch behavior.
