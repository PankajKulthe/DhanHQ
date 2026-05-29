from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.trading import BrokerLoginRequest, BrokerStatus
from app.services.auth_service import broker_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/broker/login", response_model=BrokerStatus)
def broker_login(payload: BrokerLoginRequest, db: Session = Depends(get_db)) -> BrokerStatus:
    session = broker_auth_service.login(db, payload.api_key, payload.client_code, payload.password, payload.totp, payload.totp_secret)
    return BrokerStatus(connected=True, client_code=session.client_code, feed_connected=False, message="Angel One session generated")


@router.get("/broker/status", response_model=BrokerStatus)
def broker_status() -> BrokerStatus:
    return BrokerStatus(**broker_auth_service.status())
