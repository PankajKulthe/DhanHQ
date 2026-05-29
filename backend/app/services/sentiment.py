from app.schemas.trading import StrategyConfig


class NiftyBreadthSentimentEngine:
    def score(self, filtered_stocks: list[dict], config: StrategyConfig) -> dict:
        bullish = bearish = neutral = 0
        details = []
        for stock in filtered_stocks:
            option = stock.get("atm_ce") if stock.get("bias") == "BULLISH" else stock.get("atm_pe")
            score = 0
            if option:
                above_cpr = option.get("premium", 0) > option.get("cpr_tc", 0)
                above_vwap = option.get("premium", 0) > option.get("vwap", 0)
                momentum = bool(option.get("positive_momentum"))
                volume_ok = option.get("volume", 0) >= config.min_volume
                if stock.get("bias") == "BULLISH" and above_cpr and above_vwap and momentum and volume_ok:
                    score = 1
                    bullish += 1
                elif stock.get("bias") == "BEARISH" and above_cpr and above_vwap and momentum and volume_ok:
                    score = -1
                    bearish += 1
                else:
                    neutral += 1
            else:
                neutral += 1
            details.append({"symbol": stock.get("symbol"), "bias": stock.get("bias"), "score": score})
        breadth = bullish - bearish
        if breadth > config.positive_breadth_threshold:
            sentiment = "BULLISH"
        elif breadth < config.negative_breadth_threshold:
            sentiment = "BEARISH"
        else:
            sentiment = "SIDEWAYS"
        return {"sentiment": sentiment, "breadth_score": breadth, "bullish_count": bullish, "bearish_count": bearish, "neutral_count": neutral, "details": details}
