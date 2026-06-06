from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.trading import ScanResult, StrategyConfig
from app.services.auth_service import broker_auth_service
from app.services.dhan_scanner import DhanMarketScanner

router = APIRouter(prefix="/market", tags=["market"])


@router.post("/scan", response_model=ScanResult)
def scan_market(config: StrategyConfig, db: Session = Depends(get_db)) -> ScanResult:
    broker = broker_auth_service.ensure_broker(db)
    if not broker:
        raise HTTPException(status_code=400, detail="Dhan is not connected")
    try:
        return ScanResult(**DhanMarketScanner(broker).scan(db, config))
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
