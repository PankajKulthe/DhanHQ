import logging
import httpx
from app.core.config import get_settings

logger = logging.getLogger(__name__)


class AlertService:
    def send_telegram(self, message: str) -> bool:
        settings = get_settings()
        if not settings.telegram_bot_token or not settings.telegram_chat_id:
            return False
        try:
            response = httpx.post(
                f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage",
                json={"chat_id": settings.telegram_chat_id, "text": message},
                timeout=10,
            )
            response.raise_for_status()
            return True
        except Exception as exc:
            logger.warning("Telegram alert failed: %s", exc)
            return False


alert_service = AlertService()
