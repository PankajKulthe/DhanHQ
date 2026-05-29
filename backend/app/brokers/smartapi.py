import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import pyotp
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

try:
    from SmartApi import SmartConnect
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2
except Exception:  # pragma: no cover - SDK import depends on optional install
    SmartConnect = None
    SmartWebSocketV2 = None

logger = logging.getLogger(__name__)


class SmartAPIError(RuntimeError):
    pass


@dataclass
class SmartSession:
    jwt_token: str
    refresh_token: str
    feed_token: str
    client_code: str
    expires_at: datetime


class AngelOneBroker:
    """Thin, retrying adapter around Angel One SmartAPI.

    Official docs confirm loginByPassword/generateTokens, WebSocket 2.0 at
    wss://smartapisocket.angelone.in/smart-stream, 30 second ping/pong heartbeats,
    and a cumulative 9 requests/sec order API limit. This adapter keeps those
    constraints outside strategy code.
    """

    def __init__(self, api_key: str):
        if SmartConnect is None:
            raise SmartAPIError("smartapi-python is not installed")
        self.api_key = api_key
        self.client = SmartConnect(api_key=api_key)
        self.session: SmartSession | None = None
        self.ws: Any | None = None

    def _totp(self, totp: str | None, totp_secret: str | None) -> str:
        if totp:
            return totp
        if totp_secret:
            return pyotp.TOTP(totp_secret).now()
        raise SmartAPIError("TOTP or TOTP secret is required")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, min=0.5, max=5), retry=retry_if_exception_type(SmartAPIError))
    def login(self, client_code: str, password: str, totp: str | None = None, totp_secret: str | None = None) -> SmartSession:
        response = self.client.generateSession(client_code, password, self._totp(totp, totp_secret))
        if not response or response.get("status") is False:
            raise SmartAPIError(response.get("message", "Angel One login failed") if isinstance(response, dict) else "Angel One login failed")
        data = response["data"]
        self.session = SmartSession(
            jwt_token=data["jwtToken"],
            refresh_token=data["refreshToken"],
            feed_token=data["feedToken"],
            client_code=client_code,
            expires_at=datetime.utcnow().replace(hour=18, minute=30, second=0, microsecond=0),
        )
        return self.session

    def refresh(self) -> SmartSession:
        if not self.session:
            raise SmartAPIError("No active session")
        response = self.client.generateToken(self.session.refresh_token)
        if not response or response.get("status") is False:
            raise SmartAPIError("Token refresh failed")
        data = response["data"]
        self.session.jwt_token = data["jwtToken"]
        self.session.feed_token = data.get("feedToken", self.session.feed_token)
        self.session.expires_at = datetime.utcnow() + timedelta(hours=6)
        return self.session

    def ensure_session(self) -> SmartSession:
        if not self.session:
            raise SmartAPIError("Broker is not logged in")
        if self.session.expires_at <= datetime.utcnow() + timedelta(minutes=5):
            return self.refresh()
        return self.session

    def profile(self) -> dict:
        self.ensure_session()
        return self.client.getProfile(self.session.refresh_token)

    def quote(self, exchange_tokens: dict[str, list[str]], mode: str = "FULL") -> dict:
        self.ensure_session()
        return self.client.getMarketData(mode, exchange_tokens)

    def candle_data(self, exchange: str, token: str, interval: str, from_date: str, to_date: str) -> list[list[Any]]:
        self.ensure_session()
        response = self.client.getCandleData({"exchange": exchange, "symboltoken": token, "interval": interval, "fromdate": from_date, "todate": to_date})
        if response.get("status") is False:
            raise SmartAPIError(response.get("message", "Candle request failed"))
        return response.get("data", [])

    def place_order(self, payload: dict) -> str:
        self.ensure_session()
        order_id = self.client.placeOrder(payload)
        if not order_id:
            raise SmartAPIError("Order placement returned no order id")
        return str(order_id)

    async def connect_websocket(self, on_tick) -> None:
        session = self.ensure_session()
        if SmartWebSocketV2 is None:
            raise SmartAPIError("SmartWebSocketV2 is unavailable")
        self.ws = SmartWebSocketV2(session.jwt_token, self.api_key, session.client_code, session.feed_token)
        self.ws.on_data = lambda _ws, message: on_tick(message)
        self.ws.on_error = lambda _ws, error: logger.error("SmartAPI websocket error: %s", error)
        self.ws.on_close = lambda _ws: logger.warning("SmartAPI websocket closed")
        await asyncio.to_thread(self.ws.connect)
