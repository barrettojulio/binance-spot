def classify_zone(settings, metrics, order, scores) -> str:
    sig = settings.get("signals", {})
    vol_min = float(sig.get("vol_vs_avg_min", 1.3))
    d_min = float(sig.get("taker_buy_dom_min", 0.55))
    ob_min = float(sig.get("ob_imb_bid_min", 0.55))
    near_mult = float(sig.get("near_sma_mult", 1.05))
    lanes = settings.get("lanes", {})
    buy_th = float(lanes.get("top20", {}).get("buy_threshold", 65))
    vol_vs_avg = (metrics.quote_vol_last / max(1e-9, metrics.quote_vol_avg_12m)) if metrics.quote_vol_avg_12m else 0.0
    price_ratio = (metrics.close / max(1e-9, metrics.sma200)) if metrics.sma200 else 9.99
    conditions = [scores.buy_score >= buy_th, vol_vs_avg >= vol_min, (order.taker_buy_dom or 0.0) >= d_min, (order.ob_imb_bid or 0.0) >= ob_min, price_ratio <= near_mult]
    return "ACCUMULATION" if all(conditions) else "NEUTRAL"
