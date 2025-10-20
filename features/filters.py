from core.types import QualityFlags

def pass_quality_filters(settings, metrics) -> QualityFlags:
    q = settings.get("quality", {})
    min_vol = float(q.get("min_avg_vol_usd", 10_000_000))
    max_atr = float(q.get("max_atr_pct", 18))
    liquidity_ok = (metrics.quote_vol_avg_12m or 0.0) >= min_vol
    atr_ok = (metrics.atr_pct or 999.0) <= max_atr
    return QualityFlags(liquidity_ok=liquidity_ok, atr_ok=atr_ok, tradable=True)
