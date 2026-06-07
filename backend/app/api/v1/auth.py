import secrets
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.security import create_app_session_token, verify_app_session_token
from app.database.session import get_db
from app.schemas.trading import BrokerLoginRequest, BrokerStatus
from app.services.auth_service import broker_auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class AppLoginRequest(BaseModel):
    password: str


@router.get("/app/status")
def app_status(request: Request) -> dict:
    settings = get_settings()
    if not settings.app_access_password:
        return {"enabled": False, "unlocked": True}
    token = request.cookies.get(settings.app_session_cookie)
    return {"enabled": True, "unlocked": verify_app_session_token(token)}


@router.post("/app/login")
def app_login(payload: AppLoginRequest, response: Response) -> dict:
    settings = get_settings()
    if not settings.app_access_password:
        return {"enabled": False, "unlocked": True}
    if not secrets.compare_digest(payload.password, settings.app_access_password):
        raise HTTPException(status_code=401, detail="Invalid app password")
    response.set_cookie(
        settings.app_session_cookie,
        create_app_session_token(),
        max_age=settings.app_session_minutes * 60,
        httponly=True,
        samesite="lax",
    )
    return {"enabled": True, "unlocked": True}


@router.post("/app/logout")
def app_logout(response: Response) -> dict:
    settings = get_settings()
    response.delete_cookie(settings.app_session_cookie)
    return {"unlocked": False}


@router.post("/broker/login", response_model=BrokerStatus)
def broker_login(payload: BrokerLoginRequest, db: Session = Depends(get_db)) -> BrokerStatus:
    dhan_client_id = payload.client_id or payload.dhan_client_id or payload.client_code
    access_token = payload.access_token or payload.accessToken
    pin = payload.pin or payload.password
    if not dhan_client_id:
        raise HTTPException(status_code=400, detail="Dhan Client ID is required")
    try:
        session = broker_auth_service.login(
            db,
            dhan_client_id=dhan_client_id,
            access_token=access_token,
            pin=pin,
            totp=payload.totp,
            totp_secret=payload.totp_secret,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return BrokerStatus(connected=True, client_code=session.client_code, feed_connected=False, message="Dhan connected")


@router.get("/broker/status", response_model=BrokerStatus)
def broker_status(db: Session = Depends(get_db)) -> BrokerStatus:
    return BrokerStatus(**broker_auth_service.status(db))


@router.get("/broker/profile")
def broker_profile(db: Session = Depends(get_db)) -> dict:
    try:
        broker_auth_service.ensure_broker(db)
        return broker_auth_service.profile()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/broker/funds")
def broker_funds(db: Session = Depends(get_db)) -> dict:
    try:
        broker_auth_service.ensure_broker(db)
        return broker_auth_service.fund_limit()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
