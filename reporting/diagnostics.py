import os
import csv
import datetime as dt

def _reason_and_flags(settings, m, o, score):
    """
    Devuelve (reason:str, flags:dict, thresholds:dict) evaluando si la señal cumple umbrales.
    - m: SymbolMetrics
    - o: OrderFlow
    - score: Scores
    """
    sig = settings.get("signals", {})
    vol_min = float(sig.get("vol_vs_avg_min", 1.3))
    d_min   = float(sig.get("taker_buy_dom_min", 0.55))
    ob_min  = float(sig.get("ob_imb_bid_min", 0.55))
    near_k  = float(sig.get("near_sma_mult", 1.05))

    lanes = settings.get("lanes", {})
    buy_th = float(lanes.get("top20", {}).get("buy_threshold", 65))

    vol_vs_avg  = (m.quote_vol_last / max(1e-9, m.quote_vol_avg_12m)) if m.quote_vol_avg_12m else 0.0
    price_ratio = (m.close / max(1e-9, m.sma200)) if m.sma200 else 9.99

    near_ok  = price_ratio <= near_k
    score_ok = (getattr(score, "buy_score", 0) or 0) >= buy_th
    vol_ok   = vol_vs_avg >= vol_min
    d_ok     = (getattr(o, "taker_buy_dom", 0) or 0) >= d_min
    ob_ok    = (getattr(o, "ob_imb_bid", 0) or 0) >= ob_min

    flags = dict(
        score_ok=score_ok,
        vol_ok=vol_ok,
        taker_buy_dom_ok=d_ok,
        ob_bid_ok=ob_ok,
        near_sma200_ok=near_ok,
    )
    failed = [k for k, ok in flags.items() if not ok]
    reason = "OK" if not failed else "Failed: " + ", ".join(failed)

    thresholds = dict(
        buy_threshold=buy_th,
        vol_vs_avg_min=vol_min,
        taker_buy_dom_min=d_min,
        ob_imb_bid_min=ob_min,
        near_sma_mult=near_k,
    )
    return reason, flags, thresholds


def export_diagnostics(persistence, settings, rows, eligible, lane_decisions):
    """
    CSV compacto (solo símbolos evaluados que pasaron filtros de calidad).
    Columnas: symbol, buy_score, zone, taker_buy_dom, ob_imb_bid, vol_last, vol_avg_12m
    """
    os.makedirs("data/snapshots", exist_ok=True)
    ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = f"data/snapshots/diagnostics_{ts}.csv"

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "symbol","zone","buy_score",
            "taker_buy_dom","ob_imb_bid",
            "quote_vol_last","quote_vol_avg_12m"
        ])
        for sym, metrics, order, scores, zone in rows:
            w.writerow([
                sym, zone, f"{scores.buy_score:.2f}",
                f"{order.taker_buy_dom:.3f}", f"{order.ob_imb_bid:.3f}",
                f"{metrics.quote_vol_last:.2f}", f"{metrics.quote_vol_avg_12m:.2f}"
            ])

    return path


def export_diagnostics_full(settings, scanned_rows, out_dir="data/snapshots"):
    """
    CSV completo (incluye TODO el universo cruzado):
      - phase: "FILTERED" (no pasó calidad / error) o "EVALUATED" (pasó calidad)
      - decision_reason: para EVALUATED usa _reason_and_flags; para FILTERED incluye causa (liquidity / atr / exception)
    scanned_rows: lista de dict con:
      {symbol, phase, metrics, qflags, order|None, scores|None, zone|None, fail_reason|None}
    """
    os.makedirs(out_dir, exist_ok=True)
    ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = f"{out_dir}/diagnostics_full_{ts}.csv"

    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "symbol","phase","zone","buy_score",
            "close","sma50","sma200","price_over_sma200",
            "atr_pct","quote_vol_last","quote_vol_avg_12m","vol_vs_avg",
            "taker_buy_dom","ob_imb_bid","cvd_notional",
            "quality_liquidity_ok","quality_atr_ok","quality_tradable",
            "decision_reason","thresholds"
        ])
        for r in scanned_rows:
            m = r.get("metrics")
            q = r.get("qflags")
            o = r.get("order")
            s = r.get("scores")
            zone = r.get("zone") or ""
            phase = r.get("phase")
            fail_reason = r.get("fail_reason")

            # métricas defensivas (si m es None por excepción)
            close = getattr(m, "close", 0.0) or 0.0
            sma50 = getattr(m, "sma50", 0.0) or 0.0
            sma200 = getattr(m, "sma200", 0.0) or 0.0
            atr_pct = getattr(m, "atr_pct", 0.0) or 0.0
            qv_last = getattr(m, "quote_vol_last", 0.0) or 0.0
            qv_avg  = getattr(m, "quote_vol_avg_12m", 0.0) or 0.0
            vol_vs_avg  = (qv_last / max(1e-9, qv_avg)) if qv_avg else 0.0
            price_ratio = (close / max(1e-9, sma200)) if sma200 else 9.99

            tbd = getattr(o, "taker_buy_dom", 0.0) if o else 0.0
            obb = getattr(o, "ob_imb_bid", 0.0) if o else 0.0
            cvd = getattr(o, "cvd_notional", 0.0) if o else 0.0
            buy_score = getattr(s, "buy_score", 0.0) if s else 0.0

            liq_ok = int(getattr(q, "liquidity_ok", False)) if q else 0
            atr_ok = int(getattr(q, "atr_ok", False)) if q else 0
            trad_ok = int(getattr(q, "tradable", False)) if q else 0

            if phase == "EVALUATED" and s is not None and o is not None:
                reason, _, th = _reason_and_flags(settings, m, o, s)
            else:
                reason = fail_reason or "Filtered before scoring"
                th = {}

            w.writerow([
                r.get("symbol"), phase, zone, f"{buy_score:.2f}",
                f"{close:.8f}", f"{sma50:.8f}", f"{sma200:.8f}", f"{price_ratio:.4f}",
                f"{atr_pct:.2f}", f"{qv_last:.2f}", f"{qv_avg:.2f}", f"{vol_vs_avg:.3f}",
                f"{tbd:.3f}", f"{obb:.3f}", f"{cvd:.2f}",
                liq_ok, atr_ok, trad_ok,
                reason, th
            ])

    return path
