from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.analytics.daily import DailyAnalyticsEngine
from app.database.session import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/daily")
def daily(trade_date: date | None = None, db: Session = Depends(get_db)) -> dict:
    return DailyAnalyticsEngine().snapshot(db, trade_date or date.today())
