from datetime import datetime
from sqlalchemy.orm import Session
from app.brokers.dhan import DhanBroker, DhanSession
from app.core.config import get_settings
from app.core.security import decrypt_secret, encrypt_secret
from app.models.entities import BrokerSession


class BrokerAuthService:
    def __init__(self) -> None:
        self._broker: DhanBroker | None = None

    @property
    def broker(self) -> DhanBroker | None:
        return self._broker

    def ensure_broker(self, db: Session | None = None) -> DhanBroker | None:
        if self._broker and self._broker.session and self._broker.session.expires_at > datetime.utcnow():
            return self._broker
        if db is None:
            return self._broker
        stored = (
            db.query(BrokerSession)
            .filter(
                BrokerSession.broker == "DHAN",
                BrokerSession.is_active.is_(True),
                BrokerSession.expires_at > datetime.utcnow(),
            )
            .order_by(BrokerSession.id.desc())
            .first()
        )
        if not stored:
            settings = get_settings()
            if settings.dhan_client_id and settings.dhan_access_token:
                broker = DhanBroker(settings.dhan_client_id, access_token=settings.dhan_access_token)
                try:
                    profile = broker.profile()
                    broker.session.profile = profile
                except Exception:
                    self._broker = None
                    return None
                self._broker = broker
                return self._broker
            self._broker = None
            return None
        access_token = decrypt_secret(stored.jwt_token_enc)
        if not access_token:
            self._broker = None
            return None
        broker = DhanBroker(stored.client_code, access_token=access_token)
        try:
            profile = broker.profile()
            broker.session.profile = profile
        except Exception:
            stored.is_active = False
            db.commit()
            self._broker = None
            return None
        self._broker = broker
        return self._broker

    def login(
        self,
        db: Session,
        dhan_client_id: str,
        access_token: str | None = None,
        pin: str | None = None,
        totp: str | None = None,
        totp_secret: str | None = None,
    ) -> DhanSession:
        self._broker = DhanBroker(dhan_client_id)
        session = self._broker.login(access_token=access_token, pin=pin, totp=totp, totp_secret=totp_secret)
        db.add(
            BrokerSession(
                broker="DHAN",
                client_code=dhan_client_id,
                jwt_token_enc=encrypt_secret(session.access_token),
                refresh_token_enc=encrypt_secret(""),
                feed_token_enc=encrypt_secret(""),
                expires_at=session.expires_at,
            )
        )
        db.commit()
        return session

    def status(self, db: Session | None = None) -> dict:
        broker = self.ensure_broker(db)
        connected = bool(broker and broker.session and broker.session.expires_at > datetime.utcnow())
        profile = broker.session.profile if connected and broker and broker.session else {}
        data_plan = str(profile.get("dataPlan") or "") if isinstance(profile, dict) else ""
        message = "Dhan connected"
        if connected and data_plan and data_plan.upper() != "ACTIVE":
            message = f"Dhan connected; Data API {data_plan}"
        if not connected:
            message = "Dhan disconnected"
        return {
            "broker": "DHAN",
            "connected": connected,
            "client_code": broker.session.client_code if connected and broker and broker.session else None,
            "feed_connected": bool(broker and broker.ws),
            "message": message,
            "active_segment": profile.get("activeSegment") if isinstance(profile, dict) else None,
            "data_plan": data_plan or None,
            "data_validity": profile.get("dataValidity") if isinstance(profile, dict) else None,
            "token_expires_at": broker.session.expires_at if connected and broker and broker.session else None,
        }

    def profile(self) -> dict:
        if not self._broker:
            raise RuntimeError("Dhan is not connected")
        return self._broker.profile()

    def fund_limit(self) -> dict:
        if not self._broker:
            raise RuntimeError("Dhan is not connected")
        return self._broker.fund_limit()


broker_auth_service = BrokerAuthService()
