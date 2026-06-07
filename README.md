# Dhan Options Trading Platform

Production-oriented full-stack scaffold for Indian options trading on DhanHQ API v2.

## What Is Included

- FastAPI backend with SQLAlchemy models for symbols, candles, option chain, daily activity, Nifty sentiment, strategy signals, trades, positions, and trade logs.
- DhanHQ API v2 adapter for access-token login, profile/funds verification, market quote, historical candles, and order placement.
- Nifty 50 filtering, breadth sentiment, option eligibility checks, opening-range breakout strategy, risk sizing, paper/live execution boundary, backtesting metrics, and daily analytics.
- React + TypeScript dashboard with broker connection, market scan, risk state, TradingView chart, and Recharts widgets.
- PostgreSQL, Redis, Celery worker/beat, Docker Compose, environment-driven configuration, and JSON logging.

For the complete product explanation, current working status, strategy flow, modules, limitations, and roadmap, read [docs/PRODUCT_OVERVIEW.md](docs/PRODUCT_OVERVIEW.md).

## Safety Defaults

Live trading is disabled unless `LIVE_TRADING_ENABLED=true` is set. The execution layer also requires an idempotency key per trade to prevent duplicate orders. Use paper mode until Dhan credentials, symbols, lot sizes, and order payloads have been verified against your Dhan account.

## Quick Start

```bash
copy .env.example .env
docker compose up --build
```

Open:

- Backend: http://localhost:8000/docs
- Frontend: http://localhost:5173

## DhanHQ Notes

Dhan login uses a Client ID plus either a 24-hour access token from Dhan Web or PIN + TOTP token generation. Quote calls use `/marketfeed/quote`, historical candles use `/charts/historical` and `/charts/intraday`, and real order placement requires Dhan static IP whitelisting.

## Next Hardening Steps

1. Add Alembic migrations before production deployment.
2. Promote the Dhan instrument master cache into a scheduled database sync.
3. Wire Celery tasks to real market data collection windows.
4. Add exchange holiday calendar and expiry rollover rules.
5. Add broker postback endpoint for order status reconciliation.
6. Add full WebSocket subscription management and tick-to-candle aggregation.
7. Expand tests around duplicate order prevention, SL placement failures, and daily kill switch behavior.
