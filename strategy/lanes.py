def decide_lanes(settings, rows):
    out = {"BTC":"PAUSE","ETH":"PAUSE"}
    for sym, _, _, _, zone in rows:
        if sym == "BTCUSDT" and zone == "ACCUMULATION": out["BTC"] = "BUY"
        if sym == "ETHUSDT" and zone == "ACCUMULATION": out["ETH"] = "BUY"
    return out
