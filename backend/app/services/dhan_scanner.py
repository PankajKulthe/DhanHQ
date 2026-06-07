import csv
import io
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.brokers.dhan import DhanBroker
from app.models.entities import FilteredStockSnapshot, MarketSentiment, OptionWatchlistSnapshot, ScannedOptionSnapshot, StockSentimentSnapshot
from app.schemas.trading import StrategyConfig


SCRIP_MASTER_URL = "https://images.dhan.co/api-data/api-scrip-master.csv"
INDEX_CONSTITUENT_URLS = {
    "NIFTY_50": "https://niftyindices.com/IndexConstituent/ind_nifty50list.csv",
    "NIFTY_NEXT_50": "https://niftyindices.com/IndexConstituent/ind_niftynext50list.csv",
}
INDEX_NAMES = {
    "NIFTY_50": "Nifty 50",
    "NIFTY_NEXT_50": "Nifty Next 50",
}
NIFTY_50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE",
    "BAJAJFINSV", "BEL", "BPCL", "BHARTIARTL", "BRITANNIA", "CIPLA", "COALINDIA", "DRREDDY",
    "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO",
    "HINDUNILVR", "ICICIBANK", "ITC", "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT",
    "M&M", "MARUTI", "NTPC", "NESTLEIND", "ONGC", "POWERGRID", "RELIANCE", "SBILIFE",
    "SHRIRAMFIN", "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS", "TATASTEEL",
    "TECHM", "TITAN", "TRENT", "ULTRACEMCO", "WIPRO",
]
NIFTY_NEXT_50_FALLBACK = [
    "ABB", "ADANIENSOL", "ADANIGREEN", "ADANIPOWER", "AMBUJACEM", "DMART", "BAJAJHLDNG",
    "BANKBARODA", "BPCL", "BOSCHLTD", "BRITANNIA", "CGPOWER", "CANBK", "CHOLAFIN",
    "CUMMINSIND", "DLF", "DIVISLAB", "GAIL", "GODREJCP", "HDFCAMC", "HAL", "HINDZINC",
    "HYUNDAI", "INDHOTEL", "IOC", "IRFC", "JINDALSTEL", "LTM", "LODHA", "MAZDOCK",
    "MUTHOOTFIN", "PIDILITIND", "PFC", "PNB", "RECLTD", "MOTHERSON", "SHREECEM", "ENRIN",
    "SIEMENS", "SOLARINDS", "TVSMOTOR", "TATACAP", "TMCV", "TATAPOWER", "TORNTPHARM",
    "UNIONBANK", "UNITDSPR", "VBL", "VEDL", "ZYDUSLIFE",
]
INDEX_FALLBACKS = {
    "NIFTY_50": NIFTY_50,
    "NIFTY_NEXT_50": NIFTY_NEXT_50_FALLBACK,
}
SECTOR_MAP = {
    "ADANIENT": "Metals", "ADANIPORTS": "Infrastructure", "APOLLOHOSP": "Healthcare", "ASIANPAINT": "Consumer",
    "AXISBANK": "Banking", "BAJAJ-AUTO": "Auto", "BAJFINANCE": "Financials", "BAJAJFINSV": "Financials",
    "BEL": "Industrials", "BPCL": "Energy", "BHARTIARTL": "Telecom", "BRITANNIA": "Consumer", "CIPLA": "Healthcare",
    "COALINDIA": "Energy", "DRREDDY": "Healthcare", "EICHERMOT": "Auto", "GRASIM": "Cement", "HCLTECH": "IT",
    "HDFCBANK": "Banking", "HDFCLIFE": "Insurance", "HEROMOTOCO": "Auto", "HINDALCO": "Metals", "HINDUNILVR": "Consumer",
    "ICICIBANK": "Banking", "ITC": "Consumer", "INDUSINDBK": "Banking", "INFY": "IT", "JSWSTEEL": "Metals",
    "KOTAKBANK": "Banking", "LT": "Infrastructure", "M&M": "Auto", "MARUTI": "Auto", "NTPC": "Utilities",
    "NESTLEIND": "Consumer", "ONGC": "Energy", "POWERGRID": "Utilities", "RELIANCE": "Energy", "SBILIFE": "Insurance",
    "SHRIRAMFIN": "Financials", "SBIN": "Banking", "SUNPHARMA": "Healthcare", "TCS": "IT", "TATACONSUM": "Consumer",
    "TATAMOTORS": "Auto", "TATASTEEL": "Metals", "TECHM": "IT", "TITAN": "Consumer", "TRENT": "Consumer",
    "ULTRACEMCO": "Cement", "WIPRO": "IT",
}


@dataclass(frozen=True)
class DhanInstrument:
    exchange: str
    segment: str
    security_id: str
    instrument_name: str
    trading_symbol: str
    custom_symbol: str
    expiry_date: str
    strike: float
    option_type: str
    lot_size: int
    series: str
    symbol_name: str


@dataclass
class ScripIndexes:
    loaded_at: datetime
    by_security_id: dict[str, DhanInstrument]
    equities: dict[str, DhanInstrument]
    options: dict[str, list[DhanInstrument]]


_scrip_indexes: ScripIndexes | None = None
_index_symbol_cache: dict[str, tuple[datetime, list[str]]] = {}
_cpr_cache: dict[str, dict[str, Any]] = {}
_filter_state: dict[str, dict[str, Any]] = {}


def numeric(value: Any, default: float = 0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def parse_expiry(value: str) -> date | None:
    if not value:
        return None
    clean = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(clean[:10], fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(clean).date()
    except ValueError:
        return None


def previous_trading_day(today: date | None = None) -> date:
    current = today or datetime.now().date()
    current -= timedelta(days=1)
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def add_days(day: date, days: int) -> str:
    return (day + timedelta(days=days)).isoformat()


def normalize_instrument(row: dict[str, str]) -> DhanInstrument:
    return DhanInstrument(
        exchange=(row.get("SEM_EXM_EXCH_ID") or row.get("EXCH_ID") or "").strip(),
        segment=(row.get("SEM_SEGMENT") or row.get("SEGMENT") or "").strip(),
        security_id=str(row.get("SEM_SMST_SECURITY_ID") or row.get("SECURITY_ID") or "").strip(),
        instrument_name=(row.get("SEM_INSTRUMENT_NAME") or row.get("INSTRUMENT") or "").strip(),
        trading_symbol=(row.get("SEM_TRADING_SYMBOL") or row.get("TRADING_SYMBOL") or "").strip(),
        custom_symbol=(row.get("SEM_CUSTOM_SYMBOL") or row.get("DISPLAY_NAME") or "").strip(),
        expiry_date=(row.get("SEM_EXPIRY_DATE") or row.get("SM_EXPIRY_DATE") or "").strip(),
        strike=numeric(row.get("SEM_STRIKE_PRICE") or row.get("STRIKE_PRICE")),
        option_type=(row.get("SEM_OPTION_TYPE") or row.get("OPTION_TYPE") or "").strip().upper(),
        lot_size=int(numeric(row.get("SEM_LOT_UNITS") or row.get("LOT_SIZE"), 1)),
        series=(row.get("SEM_SERIES") or row.get("SERIES") or "").strip(),
        symbol_name=(row.get("SM_SYMBOL_NAME") or row.get("SYMBOL_NAME") or "").strip(),
    )


def fetch_index_symbols(universe: str) -> list[str]:
    key = universe if universe in INDEX_CONSTITUENT_URLS else "NIFTY_50"
    cached = _index_symbol_cache.get(key)
    if cached and (datetime.utcnow() - cached[0]).total_seconds() < 60 * 60 * 6:
        return cached[1]
    fallback = INDEX_FALLBACKS.get(key, NIFTY_50)
    try:
        response = httpx.get(
            INDEX_CONSTITUENT_URLS[key],
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "text/csv,application/csv,text/plain,*/*",
                "Referer": "https://niftyindices.com/",
            },
            timeout=30,
            follow_redirects=True,
        )
        response.raise_for_status()
        reader = csv.DictReader(io.StringIO(response.text.lstrip("\ufeff")))
        symbols = [
            (row.get("Symbol") or row.get("SYMBOL") or row.get("symbol") or "").strip().upper()
            for row in reader
        ]
        symbols = [symbol for symbol in symbols if symbol and not symbol.startswith("DUMMY")]
        if symbols:
            _index_symbol_cache[key] = (datetime.utcnow(), symbols)
            return symbols
    except Exception:
        pass
    symbols = list(fallback)
    _index_symbol_cache[key] = (datetime.utcnow(), symbols)
    return symbols


def load_scrip_indexes(force: bool = False) -> ScripIndexes:
    global _scrip_indexes
    if _scrip_indexes and not force:
        return _scrip_indexes

    response = httpx.get(SCRIP_MASTER_URL, timeout=60)
    response.raise_for_status()
    reader = csv.DictReader(io.StringIO(response.text))
    by_security_id: dict[str, DhanInstrument] = {}
    equities: dict[str, DhanInstrument] = {}
    options: dict[str, list[DhanInstrument]] = {}

    for raw in reader:
        row = normalize_instrument(raw)
        if row.security_id:
            by_security_id[row.security_id] = row
        exchange = row.exchange.upper()
        segment = row.segment.upper()
        instrument = row.instrument_name.upper()
        symbol = row.trading_symbol.upper()
        series = row.series.upper()

        if exchange == "NSE" and segment == "E" and instrument == "EQUITY" and series == "EQ":
            equities[symbol] = row

        if exchange == "NSE" and segment == "D" and instrument == "OPTSTK":
            underlying = symbol.split("-", 1)[0].strip().upper()
            if underlying:
                options.setdefault(underlying, []).append(row)

    _scrip_indexes = ScripIndexes(
        loaded_at=datetime.utcnow(),
        by_security_id=by_security_id,
        equities=equities,
        options=options,
    )
    return _scrip_indexes


def normalize_quote(payload: dict[str, Any] | None) -> dict[str, Any]:
    payload = payload or {}
    ltp = numeric(payload.get("last_price") or payload.get("ltp") or payload.get("lastPrice"))
    close = numeric((payload.get("ohlc") or {}).get("close") or payload.get("close") or payload.get("previousClose"))
    net_change = payload.get("net_change")
    if net_change is not None and close > 0:
        percent_change = (numeric(net_change) / close) * 100
    elif close > 0:
        percent_change = ((ltp - close) / close) * 100
    else:
        percent_change = 0
    buy_depth = (payload.get("depth") or {}).get("buy") or []
    sell_depth = (payload.get("depth") or {}).get("sell") or []
    bid = next((numeric(row.get("price")) for row in buy_depth if numeric(row.get("price")) > 0), 0)
    ask = next((numeric(row.get("price")) for row in sell_depth if numeric(row.get("price")) > 0), 0)
    spread_pct = ((ask - bid) / ltp) * 100 if bid > 0 and ask > 0 and ltp > 0 else None
    return {
        "security_id": str(payload.get("securityId") or ""),
        "ltp": round(ltp, 2),
        "close": round(close, 2),
        "percent_change": round(percent_change, 2),
        "volume": int(numeric(payload.get("volume"))),
        "oi": int(numeric(payload.get("oi"))),
        "avg_price": round(numeric(payload.get("average_price")), 2),
        "bid": round(bid, 2),
        "ask": round(ask, 2),
        "spread_pct": round(spread_pct, 2) if spread_pct is not None else None,
        "buy_quantity": int(numeric(payload.get("buy_quantity"))),
        "sell_quantity": int(numeric(payload.get("sell_quantity"))),
    }


def nearest_option_pair(indexes: ScripIndexes, underlying: str, spot: float) -> dict[str, Any] | None:
    rows = indexes.options.get(underlying, [])
    today = datetime.now().date()
    dated = []
    for row in rows:
        expiry = parse_expiry(row.expiry_date)
        option_type = row.option_type or row.trading_symbol[-2:].upper()
        if not expiry or expiry < today or option_type not in {"CE", "PE"} or row.strike <= 0:
            continue
        dated.append({"row": row, "expiry": expiry, "strike": row.strike, "option_type": option_type})
    if not dated:
        return None
    nearest_expiry = min(item["expiry"] for item in dated)
    expiry_rows = [item for item in dated if item["expiry"] == nearest_expiry]
    nearest_strike = min((item["strike"] for item in expiry_rows), key=lambda strike: abs(strike - spot))
    ce = next((item["row"] for item in expiry_rows if item["strike"] == nearest_strike and item["option_type"] == "CE"), None)
    pe = next((item["row"] for item in expiry_rows if item["strike"] == nearest_strike and item["option_type"] == "PE"), None)
    if not ce and not pe:
        return None
    return {"ce": ce, "pe": pe, "expiry": nearest_expiry.isoformat(), "strike": nearest_strike}


def cpr_from_ohlc(high: float, low: float, close: float, source: str) -> dict[str, Any] | None:
    if high <= 0 or low <= 0 or close <= 0:
        return None
    pivot = (high + low + close) / 3
    bc_raw = (high + low) / 2
    tc_raw = (pivot - bc_raw) + pivot
    return {
        "source": source,
        "high": round(high, 2),
        "low": round(low, 2),
        "close": round(close, 2),
        "pivot": round(pivot, 2),
        "bc": round(min(bc_raw, tc_raw), 2),
        "tc": round(max(bc_raw, tc_raw), 2),
    }


def cpr_from_candles(candles: list[list[Any]], source: str) -> dict[str, Any] | None:
    if not candles:
        return None
    highs = [numeric(candle[2]) for candle in candles if numeric(candle[2]) > 0]
    lows = [numeric(candle[3]) for candle in candles if numeric(candle[3]) > 0]
    close = numeric(candles[-1][4])
    if not highs or not lows:
        return None
    return cpr_from_ohlc(max(highs), min(lows), close, source)


def option_cpr(broker: DhanBroker, option: DhanInstrument, trade_day: date) -> dict[str, Any]:
    cache_key = f"{option.security_id}:{trade_day.isoformat()}"
    if cache_key in _cpr_cache:
        return _cpr_cache[cache_key]
    attempts: list[dict[str, Any]] = []
    from_date = trade_day.isoformat()
    to_date = add_days(trade_day, 1)
    try:
        candles = broker.historical_daily(option.security_id, "NSE_FNO", option.instrument_name or "OPTSTK", from_date, to_date)
        attempts.append({"source": "DAILY", "fromDate": from_date, "toDate": to_date, "count": len(candles)})
        cpr = cpr_from_candles(candles[-1:], "DHAN_DAILY")
        if cpr:
            result = {**cpr, "attempts": attempts}
            _cpr_cache[cache_key] = result
            return result
    except Exception as exc:
        attempts.append({"source": "DAILY", "fromDate": from_date, "toDate": to_date, "error": str(exc)})
    try:
        candles = broker.historical_intraday(
            option.security_id,
            "NSE_FNO",
            option.instrument_name or "OPTSTK",
            "5",
            f"{trade_day.isoformat()} 09:15:00",
            f"{trade_day.isoformat()} 15:30:00",
        )
        attempts.append({"source": "FIVE_MINUTE", "count": len(candles)})
        cpr = cpr_from_candles(candles, "DHAN_FIVE_MINUTE")
        if cpr:
            result = {**cpr, "attempts": attempts}
            _cpr_cache[cache_key] = result
            time.sleep(0.18)
            return result
    except Exception as exc:
        attempts.append({"source": "FIVE_MINUTE", "error": str(exc)})
    result = {"bc": 0, "tc": 0, "pivot": 0, "source": "UNAVAILABLE", "attempts": attempts}
    _cpr_cache[cache_key] = result
    return result


def vwap_from_candles(candles: list[list[Any]]) -> float:
    turnover = 0.0
    volume = 0.0
    for candle in candles:
        candle_volume = numeric(candle[5])
        typical = (numeric(candle[1]) + numeric(candle[2]) + numeric(candle[3]) + numeric(candle[4])) / 4
        turnover += typical * candle_volume
        volume += candle_volume
    return round(turnover / volume, 2) if volume > 0 else 0


def option_momentum(candles: list[list[Any]], premium: float, vwap: float, cpr_bottom: float) -> dict[str, Any]:
    if not candles or premium <= 0:
        return {"score": 0, "label": "NO_CANDLES", "session_move_pct": 0, "last_candle_move_pct": 0, "details": ["no_intraday_candles"]}
    first_open = numeric(candles[0][1])
    day_high = max(numeric(candle[2]) for candle in candles)
    last = candles[-1]
    last_open = numeric(last[1])
    last_high = numeric(last[2])
    last_close = numeric(last[4]) or premium
    session_move_pct = ((premium - first_open) / first_open) * 100 if first_open > 0 else 0
    last_candle_move_pct = ((last_close - last_open) / last_open) * 100 if last_open > 0 else 0
    score = 0
    details: list[str] = []
    if vwap > 0 and premium > vwap:
        score += 20
        details.append("above_vwap")
    if cpr_bottom > 0 and premium > cpr_bottom:
        score += 20
        details.append("above_cpr_bottom")
    if first_open > 0 and premium > first_open:
        score += 15
        details.append("above_session_open")
    if session_move_pct >= 5:
        score += 20
        details.append("session_move_gt_5pct")
    elif session_move_pct >= 2:
        score += 10
        details.append("session_move_gt_2pct")
    if last_close > last_open and last_high > 0 and last_close >= last_high * 0.85:
        score += 15
        details.append("latest_5m_strength")
    if day_high > 0 and premium >= day_high * 0.95:
        score += 10
        details.append("near_day_high")
    score = int(clamp(score, 0, 100))
    return {
        "score": score,
        "label": "STRONG" if score >= 70 else "MEDIUM" if score >= 50 else "WEAK",
        "session_move_pct": round(session_move_pct, 2),
        "last_candle_move_pct": round(last_candle_move_pct, 2),
        "details": details,
    }


def enhanced_sentiment(stocks: list[dict[str, Any]], bullish_count: int, bearish_count: int, total_sentiments: int) -> dict[str, Any]:
    advancing = sum(1 for stock in stocks if stock["quote"]["percent_change"] > 0)
    declining = sum(1 for stock in stocks if stock["quote"]["percent_change"] < 0)
    avg_abs_move = sum(abs(stock["quote"]["percent_change"]) for stock in stocks) / max(len(stocks), 1)
    sector_stats: dict[str, dict[str, Any]] = {}
    for stock in stocks:
        sector = SECTOR_MAP.get(stock["symbol"], "Other")
        sector_stats.setdefault(sector, {"sector": sector, "stocks": 0, "total_move": 0.0})
        sector_stats[sector]["stocks"] += 1
        sector_stats[sector]["total_move"] += stock["quote"]["percent_change"]
    sector_breadth = []
    for stat in sector_stats.values():
        sector_breadth.append({**stat, "avg_move": round(stat["total_move"] / max(stat["stocks"], 1), 2)})
    sentiment_score = round(((bullish_count - bearish_count) / max(total_sentiments, 1)) * 100, 2)
    confidence_score = round(clamp(abs(sentiment_score), 0, 100), 2)
    market_regime = (
        "HIGH_VOLATILITY" if avg_abs_move >= 2.5 else
        "TRENDING_BULLISH" if sentiment_score >= 20 else
        "TRENDING_BEARISH" if sentiment_score <= -20 else
        "LOW_VOLATILITY" if avg_abs_move <= 0.8 else
        "SIDEWAYS"
    )
    return {
        "sentiment_score": sentiment_score,
        "confidence_score": confidence_score,
        "market_regime": market_regime,
        "advancing": advancing,
        "declining": declining,
        "advance_decline_ratio": round(advancing / declining, 2) if declining else advancing,
        "sector_breadth": sector_breadth,
    }


def stock_momentum_score(stock: dict[str, Any]) -> int:
    abs_move = abs(numeric(stock.get("stock_move_percent")))
    score = 0
    if abs_move >= 2:
        score += 35
    if abs_move >= 3:
        score += 20
    if abs_move >= 4:
        score += 15
    if numeric(stock.get("ltp")) > 0 and numeric(stock.get("previous_close")) > 0:
        score += 15
    if stock.get("stock_bias") in {"BULLISH", "BEARISH"}:
        score += 15
    return int(clamp(score, 0, 100))


def smart_money_score(option: dict[str, Any]) -> dict[str, Any]:
    score = 0
    factors = {
        "option_volume_spike": numeric(option.get("volume")) >= 300000 or numeric(option.get("turnover")) >= 6000000,
        "oi_buildup": numeric(option.get("oi")) > 0 and numeric(option.get("premium")) > numeric(option.get("vwap")),
        "premium_expansion": numeric(option.get("session_move_pct")) >= 5,
        "tight_spreads": option.get("spread") is not None and numeric(option.get("spread")) <= 1.5,
        "vwap_holding": numeric(option.get("vwap")) > 0 and numeric(option.get("premium")) > numeric(option.get("vwap")),
    }
    if factors["option_volume_spike"]:
        score += 25
    if factors["oi_buildup"]:
        score += 20
    if factors["premium_expansion"]:
        score += 20
    if factors["tight_spreads"]:
        score += 15
    if factors["vwap_holding"]:
        score += 20
    return {
        "score": int(clamp(score, 0, 100)),
        "label": "STRONG_INSTITUTIONAL" if score >= 80 else "MEDIUM_PARTICIPATION" if score >= 60 else "IGNORE",
        "factors": factors,
    }


def persist_filter_lifecycle(db: Session, generated_at: datetime, stocks: list[dict[str, Any]], strong_stocks: list[dict[str, Any]], min_move: float) -> None:
    strong_by_symbol = {stock["stock_symbol"]: stock for stock in strong_stocks}
    for stock in stocks:
        symbol = stock["symbol"]
        active = _filter_state.get(symbol)
        strong = strong_by_symbol.get(symbol)
        if strong and not active:
            _filter_state[symbol] = {"entered_at": generated_at, "last_seen_at": generated_at}
            db.add(
                FilteredStockSnapshot(
                    stock_symbol=symbol,
                    stock_move_percent=strong["stock_move_percent"],
                    stock_bias=strong["stock_bias"],
                    event="ENTER_FILTER",
                    entered_at=generated_at,
                    timestamp=generated_at,
                    details={"threshold": min_move, **strong},
                )
            )
        elif strong and active:
            active["last_seen_at"] = generated_at
            db.add(
                FilteredStockSnapshot(
                    stock_symbol=symbol,
                    stock_move_percent=strong["stock_move_percent"],
                    stock_bias=strong["stock_bias"],
                    event="ACTIVE_FILTER",
                    entered_at=active["entered_at"],
                    timestamp=generated_at,
                    details={"threshold": min_move, **strong},
                )
            )
        elif not strong and active:
            _filter_state.pop(symbol, None)
            db.add(
                FilteredStockSnapshot(
                    stock_symbol=symbol,
                    stock_move_percent=stock["quote"]["percent_change"],
                    stock_bias="BULLISH" if stock["quote"]["percent_change"] >= 0 else "BEARISH",
                    event="EXIT_FILTER",
                    entered_at=active["entered_at"],
                    exited_at=generated_at,
                    timestamp=generated_at,
                    details={"threshold": min_move, "ltp": stock["quote"]["ltp"]},
                )
            )


class DhanMarketScanner:
    def __init__(self, broker: DhanBroker) -> None:
        self.broker = broker

    def scan(self, db: Session, config: StrategyConfig) -> dict[str, Any]:
        profile = self.broker.session.profile if self.broker.session else None
        if not profile:
            profile = self.broker.profile()
            if self.broker.session:
                self.broker.session.profile = profile
        data_plan = str((profile or {}).get("dataPlan") or "").strip()
        if data_plan and data_plan.upper() != "ACTIVE":
            data_validity = (profile or {}).get("dataValidity") or "NA"
            raise RuntimeError(
                f"Dhan Data API plan is {data_plan}. Stock/option scanner needs Dhan market quote API access. "
                f"Enable/renew Dhan Data API plan and login again. Data validity: {data_validity}"
            )
        active_segment = str((profile or {}).get("activeSegment") or "")
        if "E" not in active_segment or "D" not in active_segment:
            raise RuntimeError(f"Dhan account active segments do not include both Equity and Derivatives: {active_segment or 'unknown'}")
        universe = config.universe if config.universe in INDEX_NAMES else "NIFTY_50"
        index_name = INDEX_NAMES[universe]
        universe_symbols = fetch_index_symbols(universe)
        indexes = load_scrip_indexes()
        generated_at = datetime.utcnow()
        min_move = config.min_underlying_move_pct
        min_premium = config.min_premium
        min_volume = config.min_volume
        max_spread_pct = config.max_spread_pct
        min_turnover = 2_000_000
        min_momentum_score = 50
        symbols = [indexes.equities[name] for name in universe_symbols if name in indexes.equities]
        if not symbols:
            raise RuntimeError(f"No {index_name} NSE equity symbols found in Dhan instrument master")

        stock_quote_payloads = self.broker.quote_many("NSE_EQ", [symbol.security_id for symbol in symbols])
        stocks: list[dict[str, Any]] = []
        for symbol in symbols:
            quote = normalize_quote(stock_quote_payloads.get(symbol.security_id))
            if quote["ltp"] <= 0:
                continue
            stocks.append({"symbol": symbol.trading_symbol.upper(), "instrument": symbol, "quote": quote})

        atm_pairs: list[dict[str, Any]] = []
        sentiment_options: list[DhanInstrument] = []
        for stock in stocks:
            pair = nearest_option_pair(indexes, stock["symbol"], stock["quote"]["ltp"])
            if not pair:
                continue
            atm_pairs.append({"stock": stock, "pair": pair})
            if pair.get("ce"):
                sentiment_options.append(pair["ce"])
            if pair.get("pe"):
                sentiment_options.append(pair["pe"])

        option_quote_payloads = self.broker.quote_many("NSE_FNO", [option.security_id for option in sentiment_options])
        option_quotes = {token: normalize_quote(payload) for token, payload in option_quote_payloads.items()}

        cpr_day = previous_trading_day()
        cpr_by_token: dict[str, dict[str, Any]] = {}
        for option in sentiment_options:
            cpr_by_token[option.security_id] = option_cpr(self.broker, option, cpr_day)

        bullish_count = bearish_count = neutral_count = 0
        bullish_stock_list: list[str] = []
        bearish_stock_list: list[str] = []
        stock_sentiments: list[dict[str, Any]] = []
        paired_symbols = {item["stock"]["symbol"] for item in atm_pairs}

        for item in atm_pairs:
            stock = item["stock"]
            pair = item["pair"]
            ce = pair.get("ce")
            pe = pair.get("pe")
            ce_quote = option_quotes.get(ce.security_id, {}) if ce else {}
            pe_quote = option_quotes.get(pe.security_id, {}) if pe else {}
            ce_cpr = cpr_by_token.get(ce.security_id, {}) if ce else {}
            pe_cpr = cpr_by_token.get(pe.security_id, {}) if pe else {}
            ce_price = numeric(ce_quote.get("ltp"))
            pe_price = numeric(pe_quote.get("ltp"))
            ce_cpr_bottom = numeric(ce_cpr.get("bc"))
            pe_cpr_bottom = numeric(pe_cpr.get("bc"))
            ce_above = ce_cpr_bottom > 0 and ce_price > ce_cpr_bottom
            pe_above = pe_cpr_bottom > 0 and pe_price > pe_cpr_bottom
            if ce_above:
                bullish_count += 1
                bullish_stock_list.append(stock["symbol"])
            if pe_above:
                bearish_count += 1
                bearish_stock_list.append(stock["symbol"])
            if not ce_above and not pe_above:
                neutral_count += 1
            row = {
                "stock_symbol": stock["symbol"],
                "universe": universe,
                "index_name": index_name,
                "stock_move_percent": stock["quote"]["percent_change"],
                "ce_symbol": ce.trading_symbol if ce else "",
                "pe_symbol": pe.trading_symbol if pe else "",
                "ce_token": ce.security_id if ce else "",
                "pe_token": pe.security_id if pe else "",
                "ce_price": ce_price,
                "pe_price": pe_price,
                "ce_cpr_bottom": ce_cpr_bottom,
                "pe_cpr_bottom": pe_cpr_bottom,
                "ce_cpr_available": ce_cpr_bottom > 0,
                "pe_cpr_available": pe_cpr_bottom > 0,
                "ce_above_cpr_bottom": ce_above,
                "pe_above_cpr_bottom": pe_above,
                "stock_sentiment": "BULLISH_AND_BEARISH" if ce_above and pe_above else "BULLISH" if ce_above else "BEARISH" if pe_above else "NEUTRAL",
                "timestamp": generated_at.isoformat(),
            }
            stock_sentiments.append(row)
            db.add(
                StockSentimentSnapshot(
                    stock_symbol=row["stock_symbol"],
                    stock_move_percent=row["stock_move_percent"],
                    ce_price=row["ce_price"],
                    pe_price=row["pe_price"],
                    ce_cpr_bottom=row["ce_cpr_bottom"],
                    pe_cpr_bottom=row["pe_cpr_bottom"],
                    stock_sentiment=row["stock_sentiment"],
                    timestamp=generated_at,
                    details=row,
                )
            )

        for stock in stocks:
            if stock["symbol"] in paired_symbols:
                continue
            neutral_count += 1
            row = {
                "stock_symbol": stock["symbol"],
                "universe": universe,
                "index_name": index_name,
                "stock_move_percent": stock["quote"]["percent_change"],
                "ce_symbol": "",
                "pe_symbol": "",
                "ce_token": "",
                "pe_token": "",
                "ce_price": 0,
                "pe_price": 0,
                "ce_cpr_bottom": 0,
                "pe_cpr_bottom": 0,
                "ce_cpr_available": False,
                "pe_cpr_available": False,
                "ce_above_cpr_bottom": False,
                "pe_above_cpr_bottom": False,
                "stock_sentiment": "NEUTRAL",
                "reason": "ATM stock option contract unavailable in Dhan instrument master",
                "timestamp": generated_at.isoformat(),
            }
            stock_sentiments.append(row)
            db.add(
                StockSentimentSnapshot(
                    stock_symbol=row["stock_symbol"],
                    stock_move_percent=row["stock_move_percent"],
                    ce_price=0,
                    pe_price=0,
                    ce_cpr_bottom=0,
                    pe_cpr_bottom=0,
                    stock_sentiment=row["stock_sentiment"],
                    timestamp=generated_at,
                    details=row,
                )
            )

        nifty_sentiment = "POSITIVE" if bullish_count > bearish_count else "NEGATIVE" if bearish_count > bullish_count else "SIDEWAYS"
        enhanced = enhanced_sentiment(stocks, bullish_count, bearish_count, len(stock_sentiments))
        enhanced["universe"] = universe
        enhanced["index_name"] = index_name
        enhanced["index_symbols"] = universe_symbols
        db.add(
            MarketSentiment(
                timestamp=generated_at,
                bullish_count=bullish_count,
                bearish_count=bearish_count,
                neutral_count=neutral_count,
                final_sentiment=nifty_sentiment,
                details=enhanced,
            )
        )

        top_gainers = sorted(stocks, key=lambda stock: stock["quote"]["percent_change"], reverse=True)
        top_losers = sorted(stocks, key=lambda stock: stock["quote"]["percent_change"])
        strong_stocks = []
        for stock in stocks:
            move = stock["quote"]["percent_change"]
            if abs(move) < min_move:
                continue
            strong = {
                "universe": universe,
                "index_name": index_name,
                "stock_symbol": stock["symbol"],
                "trading_symbol": stock["instrument"].trading_symbol,
                "token": stock["instrument"].security_id,
                "ltp": stock["quote"]["ltp"],
                "previous_close": stock["quote"]["close"],
                "stock_move_percent": move,
                "stock_bias": "BULLISH" if move >= 0 else "BEARISH",
            }
            strong["stock_momentum_score"] = stock_momentum_score(strong)
            strong["sector"] = SECTOR_MAP.get(stock["symbol"], "Other")
            strong_stocks.append(strong)

        persist_filter_lifecycle(db, generated_at, stocks, strong_stocks, min_move)

        selected_descriptors: list[dict[str, Any]] = []
        if nifty_sentiment != "SIDEWAYS":
            for strong in strong_stocks:
                pair_record = next((item for item in atm_pairs if item["stock"]["symbol"] == strong["stock_symbol"]), None)
                if not pair_record:
                    continue
                pair = pair_record["pair"]
                if nifty_sentiment == "POSITIVE":
                    if pair.get("ce"):
                        selected_descriptors.append({"stock": pair_record["stock"], "strong": strong, "pair": pair, "option": pair["ce"], "type": "CE", "preference": "PREFERRED" if strong["stock_bias"] == "BULLISH" else "ALLOWED"})
                    if pair.get("pe"):
                        selected_descriptors.append({"stock": pair_record["stock"], "strong": strong, "pair": pair, "option": pair["pe"], "type": "PE", "preference": "PREFERRED" if strong["stock_bias"] == "BEARISH" else "ALLOWED"})
                elif nifty_sentiment == "NEGATIVE" and pair.get("pe"):
                    selected_descriptors.append({"stock": pair_record["stock"], "strong": strong, "pair": pair, "option": pair["pe"], "type": "PE", "preference": "ALLOWED"})

        selected_options: list[dict[str, Any]] = []
        today_text = datetime.now().date().isoformat()
        for descriptor in selected_descriptors:
            option: DhanInstrument = descriptor["option"]
            quote = option_quotes.get(option.security_id) or normalize_quote(self.broker.quote_many("NSE_FNO", [option.security_id]).get(option.security_id))
            cpr = cpr_by_token.get(option.security_id) or option_cpr(self.broker, option, cpr_day)
            cpr_bottom = numeric(cpr.get("bc"))
            premium = numeric(quote.get("ltp"))
            try:
                candles = self.broker.historical_intraday(option.security_id, "NSE_FNO", option.instrument_name or "OPTSTK", "5", f"{today_text} 09:15:00", f"{today_text} 15:30:00", oi=True)
            except Exception:
                candles = []
            vwap = vwap_from_candles(candles) or numeric(quote.get("avg_price"))
            momentum = option_momentum(candles, premium, vwap, cpr_bottom)
            spread = quote.get("spread_pct")
            turnover = premium * numeric(quote.get("volume"))
            cpr_status = "ABOVE_BOTTOM" if cpr_bottom > 0 and premium > cpr_bottom else "BELOW_BOTTOM" if cpr_bottom > 0 else "CPR_UNAVAILABLE"
            filters = {
                "high_volume": numeric(quote.get("volume")) >= min_volume or turnover >= min_turnover,
                "tight_spread": spread is not None and numeric(spread) <= max_spread_pct,
                "above_min_premium": premium >= min_premium,
                "above_cpr_bottom": cpr_status == "ABOVE_BOTTOM",
                "above_vwap": vwap > 0 and premium > vwap,
                "strong_momentum": momentum["score"] >= min_momentum_score,
            }
            option_row = {
                "stock_symbol": descriptor["stock"]["symbol"],
                "universe": universe,
                "index_name": index_name,
                "symbol": descriptor["stock"]["symbol"],
                "underlying": descriptor["stock"]["symbol"],
                "underlying_token": descriptor["stock"]["instrument"].security_id,
                "underlying_ltp": descriptor["stock"]["quote"]["ltp"],
                "underlying_change_pct": descriptor["stock"]["quote"]["percent_change"],
                "bias": descriptor["strong"]["stock_bias"],
                "stock_bias": descriptor["strong"]["stock_bias"],
                "option_type": descriptor["type"],
                "option_symbol": option.trading_symbol,
                "trading_symbol": option.trading_symbol,
                "option_token": option.security_id,
                "lot_size": option.lot_size,
                "expiry": descriptor["pair"]["expiry"],
                "strike": descriptor["pair"]["strike"],
                "premium": round(premium, 2),
                "volume": int(numeric(quote.get("volume"))),
                "turnover": round(turnover, 2),
                "oi": int(numeric(quote.get("oi"))),
                "vwap": round(vwap, 2),
                "bid": quote.get("bid"),
                "ask": quote.get("ask"),
                "spread": spread,
                "spread_pct": spread,
                "cpr_date": cpr_day.isoformat(),
                "cpr_bottom": cpr_bottom,
                "cpr_bc": cpr_bottom,
                "cpr_tc": numeric(cpr.get("tc")),
                "cpr_pivot": numeric(cpr.get("pivot")),
                "cpr_status": cpr_status,
                "cpr_available": cpr_bottom > 0,
                "cpr_confirmed": cpr_status == "ABOVE_BOTTOM",
                "momentum_score": momentum["score"],
                "momentum_label": momentum["label"],
                "momentum_details": momentum["details"],
                "stock_momentum_score": descriptor["strong"]["stock_momentum_score"],
                "sector": descriptor["strong"]["sector"],
                "session_move_pct": momentum["session_move_pct"],
                "last_candle_move_pct": momentum["last_candle_move_pct"],
                "preference": descriptor["preference"],
                "filters": filters,
            }
            smart = smart_money_score(option_row)
            option_row["smart_money_score"] = smart["score"]
            option_row["smart_money_label"] = smart["label"]
            option_row["smart_money_factors"] = smart["factors"]
            option_row["market_score"] = enhanced["confidence_score"]
            option_row["breakout_score"] = momentum["score"]
            option_row["final_trade_score"] = round((enhanced["confidence_score"] * 0.25) + (descriptor["strong"]["stock_momentum_score"] * 0.25) + (smart["score"] * 0.35) + (momentum["score"] * 0.15), 2)
            option_row["eligible"] = all(filters.values())
            option_row["rejection_reasons"] = [key for key, value in filters.items() if not value]
            db.add(
                ScannedOptionSnapshot(
                    stock_symbol=option_row["stock_symbol"],
                    option_symbol=option_row["option_symbol"],
                    option_type=option_row["option_type"],
                    premium=option_row["premium"],
                    volume=option_row["volume"],
                    spread=option_row["spread"],
                    vwap=option_row["vwap"],
                    cpr_status=option_row["cpr_status"],
                    momentum_score=option_row["momentum_score"],
                    smart_money_score=option_row["smart_money_score"],
                    final_trade_score=option_row["final_trade_score"],
                    eligible=option_row["eligible"],
                    timestamp=generated_at,
                    details=option_row,
                )
            )
            selected_options.append(option_row)

        final_watchlist = sorted(
            [item for item in selected_options if item["eligible"]],
            key=lambda item: (
                -numeric(item["volume"]),
                -numeric(item["momentum_score"]),
                numeric(item["spread"], 999),
                -abs(numeric(item["underlying_change_pct"])),
                -numeric(item["final_trade_score"]),
            ),
        )
        for index, row in enumerate(final_watchlist, start=1):
            row["final_rank"] = index
            db.add(
                OptionWatchlistSnapshot(
                    stock_symbol=row["stock_symbol"],
                    option_symbol=row["option_symbol"],
                    option_type=row["option_type"],
                    premium=row["premium"],
                    volume=row["volume"],
                    spread=row["spread"],
                    vwap=row["vwap"],
                    cpr_status=row["cpr_status"],
                    momentum_score=row["momentum_score"],
                    final_rank=index,
                    timestamp=generated_at,
                    details=row,
                )
            )

        db.commit()
        return {
            "generated_at": generated_at,
            "universe": universe,
            "index_name": index_name,
            "sentiment": nifty_sentiment,
            "nifty_sentiment": nifty_sentiment,
            "breadth_score": bullish_count - bearish_count,
            "bullish_count": bullish_count,
            "bearish_count": bearish_count,
            "neutral_count": neutral_count,
            "scanned_symbols": len(stocks),
            "moved_count": len(strong_stocks),
            "sentiment_score": enhanced["sentiment_score"],
            "confidence_score": enhanced["confidence_score"],
            "market_regime": enhanced["market_regime"],
            "bullish_stock_list": bullish_stock_list,
            "bearish_stock_list": bearish_stock_list,
            "stock_sentiments": stock_sentiments,
            "top_gainers": [{"stock_symbol": stock["symbol"], "stock_move_percent": stock["quote"]["percent_change"], "ltp": stock["quote"]["ltp"]} for stock in top_gainers[:10]],
            "top_losers": [{"stock_symbol": stock["symbol"], "stock_move_percent": stock["quote"]["percent_change"], "ltp": stock["quote"]["ltp"]} for stock in top_losers[:10]],
            "strong_stocks": strong_stocks,
            "selected_atm_options": selected_options,
            "final_option_watchlist": final_watchlist,
            "candidates": final_watchlist,
            "low_confidence": nifty_sentiment == "SIDEWAYS",
            "no_trade_reason": "Nifty sentiment is SIDEWAYS" if nifty_sentiment == "SIDEWAYS" else "",
        }
