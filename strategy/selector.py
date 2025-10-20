def select_top20_eligible(settings, rows):
    candidates = []
    for sym, _, _, scores, zone in rows:
        if sym in ("BTCUSDT","ETHUSDT"): continue
        if zone == "ACCUMULATION": candidates.append((sym, scores.buy_score))
    candidates.sort(key=lambda x: x[1], reverse=True)
    max_n = int(settings.get("lanes", {}).get("top20", {}).get("max_candidates", 20))
    return candidates[:max_n]
