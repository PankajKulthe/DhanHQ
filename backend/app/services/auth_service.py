from datetime import datetime
from sqlalchemy.orm import Session
from app.brokers.smartapi import AngelOneBroker, SmartSession
from app.core.security import encrypt_secret
from app.models.entities import BrokerSession


class BrokerAuthService:
    def __init__(self) -> None:
        self._broker: AngelOneBroker | None = None

    @property
    def broker(self) -> AngelOneBroker | None:
        return self._broker

    def login(self, db: Session, api_key: str, client_code: str, password: str, totp: str | None, totp_secret: str | None) -> SmartSession:
        self._broker = AngelOneBroker(api_key)
        session = self._broker.login(client_code, password, totp=totp, totp_secret=totp_secret)
        db.add(
            BrokerSession(
                client_code=client_code,
                jwt_token_enc=encrypt_secret(session.jwt_token),
                refresh_token_enc=encrypt_secret(session.refresh_token),
                feed_token_enc=encrypt_secret(session.feed_token),
                expires_at=session.expires_at,
            )
        )
        db.commit()
        return session

    def status(self) -> dict:
        broker = self._broker
        connected = bool(broker and broker.session and broker.session.expires_at > datetime.utcnow())
        return {
            "connected": connected,
            "client_code": broker.session.client_code if connected and broker and broker.session else None,
            "feed_connected": bool(broker and broker.ws),
            "message": "Connected" if connected else "Disconnected",
        }


broker_auth_service = BrokerAuthService()
