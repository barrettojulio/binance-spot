def trailing_for_lane(settings, lane: str) -> float:
    if lane == "BTC": return float(settings.get("lanes", {}).get("btc", {}).get("trailing", 0.038))*100.0
    if lane == "ETH": return float(settings.get("lanes", {}).get("eth", {}).get("trailing", 0.05))*100.0
    return float(settings.get("lanes", {}).get("top20", {}).get("trailing_default", 0.07))*100.0
