import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
import pyotp
logger = logging.getLogger(__name__)


class DhanAPIError(RuntimeError):
    pass


@dataclass
class DhanSession:
    access_token: str
    client_code: str
    expires_at: datetime
    profile: dict[str, Any] | None = None


class DhanBroker:
    """Retrying adapter around DhanHQ API v2."""

    base_url = "https://api.dhan.co/v2"
    auth_url = "https://auth.dhan.co"

    def __init__(self, dhan_client_id: str, access_token: str | None = None) -> None:
        self.dhan_client_id = dhan_client_id.strip()
        self.session: DhanSession | None = None
        self.ws: Any | None = None
        self._last_data_request_at = 0.0
        if access_token:
            self.session = DhanSession(
                access_token=access_token.strip(),
                client_code=self.dhan_client_id,
                expires_at=datetime.utcnow() + timedelta(hours=24),
            )

    def _totp(self, totp: str | None, totp_secret: str | None) -> str | None:
        if totp:
            return totp.strip()
        if totp_secret:
            return pyotp.TOTP(totp_secret).now()
        return None

    @staticmethod
    def _parse_expiry(value: str | None) -> datetime:
        if not value:
            return datetime.utcnow() + timedelta(hours=24)
        clean = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(clean)
            return parsed.replace(tzinfo=None)
        except ValueError:
            pass
        for fmt in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        return datetime.utcnow() + timedelta(hours=24)

    def _headers(self, include_client_id: bool = False) -> dict[str, str]:
        session = self.ensure_session()
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "access-token": session.access_token,
        }
        if include_client_id:
            headers["client-id"] = session.client_code
        return headers

    def _throttle(self, path: str) -> None:
        if not (path.startswith("/marketfeed/") or path.startswith("/charts/")):
            return
        minimum_gap = 1.05
        elapsed = time.monotonic() - self._last_data_request_at
        if elapsed < minimum_gap:
            time.sleep(minimum_gap - elapsed)
        self._last_data_request_at = time.monotonic()

    @staticmethod
    def _raise_for_dhan(response: httpx.Response, data: Any) -> None:
        if response.is_success and not (isinstance(data, dict) and data.get("status") in {"failure", "error"}):
            return
        if isinstance(data, dict):
            message = data.get("errorMessage") or data.get("message") or data.get("errorCode")
        else:
            message = None
        raise DhanAPIError(message or f"Dhan request failed with HTTP {response.status_code}")

    def request(self, method: str, path: str, *, json_body: dict[str, Any] | None = None, include_client_id: bool = False) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        last_error: Exception | None = None
        for attempt in range(1, 4):
            try:
                self._throttle(path)
                with httpx.Client(timeout=30) as client:
                    response = client.request(method, url, headers=self._headers(include_client_id=include_client_id), json=json_body)
                data = response.json() if response.content else {}
                self._raise_for_dhan(response, data)
                return data
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < 3:
                    time.sleep(0.5 * attempt)
                    continue
                raise DhanAPIError(str(exc)) from exc
            except DhanAPIError as exc:
                last_error = exc
                if "HTTP 429" in str(exc) and attempt < 3:
                    time.sleep(2.0 * attempt)
                    continue
                raise
        raise DhanAPIError(str(last_error) if last_error else "Dhan request failed")

    def login(self, pin: str | None = None, totp: str | None = None, totp_secret: str | None = None, access_token: str | None = None) -> DhanSession:
        if not self.dhan_client_id:
            raise DhanAPIError("Dhan Client ID is required")

        token = (access_token or "").strip()
        expiry = datetime.utcnow() + timedelta(hours=24)

        if not token:
            clean_pin = (pin or "").strip()
            clean_totp = self._totp(totp, totp_secret)
            if not (clean_pin.isdigit() and len(clean_pin) == 6):
                raise DhanAPIError("Enter your 6-digit Dhan PIN, or paste today's access token")
            if not (clean_totp and clean_totp.isdigit() and len(clean_totp) == 6):
                raise DhanAPIError("TOTP must be exactly 6 digits")
            url = f"{self.auth_url}/app/generateAccessToken"
            try:
                with httpx.Client(timeout=30) as client:
                    response = client.post(
                        url,
                        params={"dhanClientId": self.dhan_client_id, "pin": clean_pin, "totp": clean_totp},
                        headers={"accept": "application/json"},
                    )
                data = response.json() if response.content else {}
            except httpx.HTTPError as exc:
                raise DhanAPIError(str(exc)) from exc
            self._raise_for_dhan(response, data)
            token = str(data.get("accessToken") or "")
            if not token:
                raise DhanAPIError("Dhan token generation did not return an access token")
            expiry = self._parse_expiry(data.get("expiryTime"))

        self.session = DhanSession(access_token=token, client_code=self.dhan_client_id, expires_at=expiry)
        profile = self.profile()
        self.session.profile = profile
        if isinstance(profile, dict) and profile.get("tokenValidity"):
            self.session.expires_at = self._parse_expiry(str(profile.get("tokenValidity")))
        return self.session

    def ensure_session(self) -> DhanSession:
        if not self.session:
            raise DhanAPIError("Dhan is not connected")
        if self.session.expires_at <= datetime.utcnow():
            raise DhanAPIError("Dhan access token has expired")
        return self.session

    def profile(self) -> dict[str, Any]:
        return self.request("GET", "/profile")

    def fund_limit(self) -> dict[str, Any]:
        return self.request("GET", "/fundlimit")

    def orders(self) -> list[dict[str, Any]]:
        data = self.request("GET", "/orders")
        if isinstance(data, list):
            return data
        rows = data.get("data") if isinstance(data, dict) else []
        return rows if isinstance(rows, list) else []

    def order_detail(self, order_id: str) -> dict[str, Any]:
        data = self.request("GET", f"/orders/{order_id}")
        if isinstance(data, list):
            return data[0] if data else {}
        return data

    def quote(self, exchange_segment: str, security_ids: list[str | int]) -> dict[str, Any]:
        clean_ids = [int(value) if str(value).isdigit() else str(value) for value in security_ids]
        return self.request(
            "POST",
            "/marketfeed/quote",
            json_body={exchange_segment: clean_ids},
            include_client_id=True,
        )

    def quote_many(self, exchange_segment: str, security_ids: list[str | int], batch_size: int = 900) -> dict[str, dict[str, Any]]:
        results: dict[str, dict[str, Any]] = {}
        for index in range(0, len(security_ids), batch_size):
            batch = security_ids[index : index + batch_size]
            if not batch:
                continue
            data = self.quote(exchange_segment, batch)
            segment_data = data.get("data", {}).get(exchange_segment, {}) if isinstance(data, dict) else {}
            for security_id, payload in segment_data.items():
                if isinstance(payload, dict):
                    results[str(security_id)] = {**payload, "securityId": str(security_id), "exchangeSegment": exchange_segment}
            if index + batch_size < len(security_ids):
                time.sleep(1.05)
        return results

    @staticmethod
    def chart_to_candles(data: dict[str, Any]) -> list[list[Any]]:
        opens = data.get("open") or []
        highs = data.get("high") or []
        lows = data.get("low") or []
        closes = data.get("close") or []
        volumes = data.get("volume") or []
        timestamps = data.get("timestamp") or []
        oi = data.get("open_interest") or []
        candles: list[list[Any]] = []
        for index, open_price in enumerate(opens):
            timestamp = timestamps[index] if index < len(timestamps) else None
            ts_text = datetime.fromtimestamp(int(timestamp)).isoformat() if timestamp else ""
            candles.append(
                [
                    ts_text,
                    float(open_price or 0),
                    float(highs[index] if index < len(highs) else 0),
                    float(lows[index] if index < len(lows) else 0),
                    float(closes[index] if index < len(closes) else 0),
                    int(volumes[index] if index < len(volumes) else 0),
                    int(oi[index] if index < len(oi) else 0),
                ]
            )
        return candles

    def historical_daily(self, security_id: str, exchange_segment: str, instrument: str, from_date: str, to_date: str, oi: bool = False) -> list[list[Any]]:
        data = self.request(
            "POST",
            "/charts/historical",
            json_body={
                "securityId": str(security_id),
                "exchangeSegment": exchange_segment,
                "instrument": instrument,
                "expiryCode": 0,
                "oi": oi,
                "fromDate": from_date,
                "toDate": to_date,
            },
        )
        return self.chart_to_candles(data)

    def historical_intraday(
        self,
        security_id: str,
        exchange_segment: str,
        instrument: str,
        interval: str,
        from_date: str,
        to_date: str,
        oi: bool = False,
    ) -> list[list[Any]]:
        data = self.request(
            "POST",
            "/charts/intraday",
            json_body={
                "securityId": str(security_id),
                "exchangeSegment": exchange_segment,
                "instrument": instrument,
                "interval": str(interval),
                "oi": oi,
                "fromDate": from_date,
                "toDate": to_date,
            },
        )
        return self.chart_to_candles(data)

    def place_order(self, payload: dict[str, Any]) -> str:
        data = self.request("POST", "/orders", json_body=payload)
        order_id = data.get("orderId") or data.get("order_id") or data.get("id")
        if not order_id:
            raise DhanAPIError("Dhan order placement returned no order id")
        return str(order_id)
