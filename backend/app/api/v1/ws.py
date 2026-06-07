import asyncio
from datetime import date
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.analytics.daily import DailyAnalyticsEngine
from app.core.config import get_settings
from app.core.security import verify_app_session_token
from app.database.session import SessionLocal
from app.services.auth_service import broker_auth_service

router = APIRouter(prefix="/ws", tags=["websocket"])


@router.websocket("/dashboard")
async def dashboard_feed(websocket: WebSocket):
    settings = get_settings()
    if settings.app_access_password:
        token = websocket.cookies.get(settings.app_session_cookie)
        if not verify_app_session_token(token):
            await websocket.close(code=1008)
            return
    await websocket.accept()
    try:
        while True:
            db = SessionLocal()
            try:
                broker = broker_auth_service.ensure_broker(db)
                snapshot = DailyAnalyticsEngine().snapshot(db, date.today(), broker=broker)
                await websocket.send_json({"type": "dashboard", "data": snapshot})
            finally:
                db.close()
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return
