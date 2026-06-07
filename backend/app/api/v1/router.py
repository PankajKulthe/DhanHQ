from fastapi import APIRouter
from app.api.v1 import analytics, auth, backtests, historical, market, trading, ws

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(market.router)
api_router.include_router(backtests.router)
api_router.include_router(historical.router)
api_router.include_router(trading.router)
api_router.include_router(analytics.router)
api_router.include_router(ws.router)
