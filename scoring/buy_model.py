from core.types import Scores
from .normalize import clamp01

def compute_buy_score(settings, metrics, order) -> Scores:
    D = clamp01(order.taker_buy_dom)
    vol_vs_avg = (metrics.quote_vol_last / max(1e-9, metrics.quote_vol_avg_12m)) if metrics.quote_vol_avg_12m else 0.0
    V = clamp01(min(3.0, vol_vs_avg) / 3.0)
    price_ratio = (metrics.close / max(1e-9, metrics.sma200)) if metrics.sma200 else 9.99
    S = clamp01((1.05 - price_ratio) / 1.05) if price_ratio is not None else 0.0
    B = clamp01(order.ob_imb_bid)
    q = settings.get("quality", {})
    min_vol = float(q.get("min_avg_vol_usd", 10_000_000))
    max_atr = float(q.get("max_atr_pct", 18))
    P_liq = 1.0 if (metrics.quote_vol_avg_12m or 0) >= min_vol else 0.0
    P_vola = clamp01(1.0 - ((metrics.atr_pct or 0.0) / max_atr))
    wD, wV, wS, wB = 0.35, 0.30, 0.20, 0.15
    raw = wD*D + wV*V + wS*S + wB*B
    score = 100.0 * raw * P_liq * P_vola
    return Scores(buy_score=score, sell_score=0.0, zone="NEUTRAL")
