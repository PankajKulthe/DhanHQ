# API Summary

Base path: `/api/v1`

## Auth

- `POST /auth/broker/login`: generates Angel One session with client code, password, and TOTP or TOTP secret.
- `GET /auth/broker/status`: returns broker and feed connection state.

## Market

- `POST /market/scan`: runs the configured Nifty breadth and option selection pipeline.

## Trading

- `POST /trading/orders`: places a protected paper/live order using idempotency.

## Backtests

- `POST /backtests/run`: runs the opening range breakout simulator with slippage and brokerage settings.

## Analytics

- `GET /analytics/daily?trade_date=YYYY-MM-DD`: returns daily sentiment, trade, and PnL summary.
