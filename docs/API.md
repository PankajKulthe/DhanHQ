# API Summary

Base path: `/api/v1`

## Auth

- `POST /auth/broker/login`: connects Dhan using Client ID plus either access token or 6-digit PIN + TOTP.
- `GET /auth/broker/status`: returns broker and feed connection state.
- `GET /auth/broker/profile`: validates the Dhan access token and returns account API profile data.
- `GET /auth/broker/funds`: returns Dhan fund-limit data.

## Market

- `POST /market/scan`: runs the configured Nifty breadth and option selection pipeline.

## Trading

- `POST /trading/orders`: places a protected paper/live order using idempotency.

## Backtests

- `POST /backtests/run`: runs the opening range breakout simulator with slippage and brokerage settings.

## Analytics

- `GET /analytics/daily?trade_date=YYYY-MM-DD`: returns daily sentiment, trade, and PnL summary.
