from fastapi import APIRouter
from app.api.v1 import analytics, auth, backtests, market, trading

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(market.router)
api_router.include_router(backtests.router)
api_router.include_router(trading.router)
api_router.include_router(analytics.router)
