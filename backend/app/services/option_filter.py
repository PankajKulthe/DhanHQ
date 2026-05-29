from app.schemas.trading import StrategyConfig


class OptionSelectionEngine:
    def eligible(self, option: dict, sentiment: str, config: StrategyConfig) -> tuple[bool, list[str]]:
        reasons: list[str] = []
        if sentiment == "BULLISH" and option.get("type") != "CE":
            reasons.append("sentiment_allows_calls_only")
        if sentiment == "BEARISH" and option.get("type") != "PE":
            reasons.append("sentiment_allows_puts_only")
        if sentiment == "SIDEWAYS":
            reasons.append("sideways_market")
        if abs(option.get("underlying_move_pct", 0)) < config.min_underlying_move_pct:
            reasons.append("underlying_move_below_threshold")
        if option.get("premium", 0) < config.min_premium:
            reasons.append("premium_below_minimum")
        if option.get("premium", 0) <= option.get("cpr_tc", 0):
            reasons.append("premium_below_cpr")
        if option.get("premium", 0) <= option.get("vwap", 0):
            reasons.append("premium_below_vwap")
        if not option.get("positive_momentum", False):
            reasons.append("no_positive_momentum")
        if option.get("volume", 0) < config.min_volume:
            reasons.append("low_volume")
        if option.get("spread_pct", 99) > config.max_spread_pct:
            reasons.append("wide_spread")
        if option.get("oi_available") and not option.get("oi_increasing", False):
            reasons.append("oi_not_increasing")
        if option.get("manipulation_candle", False):
            reasons.append("manipulation_candle")
        return len(reasons) == 0, reasons

    def filter(self, options: list[dict], sentiment: str, config: StrategyConfig) -> list[dict]:
        selected = []
        for option in options:
            ok, reasons = self.eligible(option, sentiment, config)
            if ok:
                selected.append({**option, "selection_reasons": []})
            else:
                option["rejection_reasons"] = reasons
        return selected
