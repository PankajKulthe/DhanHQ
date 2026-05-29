from datetime import datetime
from fastapi import APIRouter
from app.schemas.trading import ScanResult, StrategyConfig
from app.services.option_filter import OptionSelectionEngine
from app.services.sentiment import NiftyBreadthSentimentEngine

router = APIRouter(prefix="/market", tags=["market"])


@router.post("/scan", response_model=ScanResult)
def scan_market(config: StrategyConfig) -> ScanResult:
    sample_filtered = []
    sentiment = NiftyBreadthSentimentEngine().score(sample_filtered, config)
    candidates = OptionSelectionEngine().filter([], sentiment["sentiment"], config)
    return ScanResult(generated_at=datetime.utcnow(), sentiment=sentiment["sentiment"], breadth_score=sentiment["breadth_score"], candidates=candidates)
