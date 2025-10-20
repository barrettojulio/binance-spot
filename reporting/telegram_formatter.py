# reporting/telegram_formatter.py
from __future__ import annotations
import datetime as dt
from typing import Dict, List, Optional, Tuple, Any

# rows: List[Tuple[symbol, metrics, order, scores, zone]]
RowT = Tuple[str, Any, Any, Any, Any]


# ---------------------------
# Helpers de formato
# ---------------------------

def _fmt_money(v: Optional[float], unit: str = "USDT") -> str:
    try:
        if v is None:
            return f"$0.00 {unit}"
        return f"${v:,.2f} {unit}"
    except Exception:
        return f"$0.00 {unit}"


def _fmt_pct(v: Optional[float]) -> str:
    try:
        return f"{100.0 * float(v):.1f} %"
    except Exception:
        return "—"


def _fmt_num(v: Optional[float], nd: int = 4) -> str:
    try:
        return f"{float(v):,.{nd}f}"
    except Exception:
        return "—"


def _get(d: dict, *path, default=None):
    cur = d
    for p in path:
        if cur is None:
            return default
        if isinstance(cur, dict) and p in cur:
            cur = cur[p]
        else:
            return default
    return cur


def _today_utc():
    return dt.datetime.utcnow().date()


def _week_range(today: Optional[dt.date] = None):
    d0 = today or _today_utc()
    d1 = d0 + dt.timedelta(days=7)
    return d0, d1


# ---------------------------
# Bloques de mensaje
# ---------------------------

def _header(total_budget: float) -> str:
    d0, d1 = _week_range()
    return (
        f"📅 Week: {d0} – {d1}\n"
        f"💰 Total budget: {_fmt_money(total_budget)}\n"
        f"\n"
    )


def _lane_block(
    title_emoji: str,
    lane_name: str,
    lane_decisions: Dict[str, str],
    allocation: Dict[str, Any],
    trailing_pct: Optional[float],
    lane_weight_pct: Optional[float],
    show_transfers: bool,
) -> str:
    # Estado (BUY / HOLD / PAUSE / NEUTRAL)
    state = lane_decisions.get(lane_name.upper(), "PAUSE")

    # Presupuesto asignado
    lane_alloc = allocation.get(lane_name.lower(), {}) if isinstance(allocation, dict) else {}
    budget_lane = lane_alloc.get("budget_total", 0.0)

    # Trailing
    trailing_line = f"Trailing Stop: {_fmt_pct(trailing_pct)}" if trailing_pct is not None else "Trailing Stop: —"

    lines = []
    lines.append("─" * 31)
    lines.append(f"{title_emoji} {lane_name}/USDT — {state.capitalize() if isinstance(state, str) else state}")
    lines.append(trailing_line)

    # Mostrar porcentaje objetivo del lane (si se proporcionó)
    if lane_weight_pct is not None:
        lines.append(f"💰 Budget: {_fmt_money(budget_lane)} ({int(round(lane_weight_pct * 100))} %)")

    # Transferencias (si corresponde)
    # Esperamos que el allocation tenga banderas o el mensaje de transferencia lo ponga el selector;
    # si no, inferimos desde lane_decisions: si está en PAUSE, asumimos transferencia.
    if show_transfers and str(state).upper() in ("PAUSE", "NEUTRAL"):
        # Cuánto % aproximado se transfiere (el weight; informativo)
        if lane_weight_pct is not None:
            lines.append(f"↪ {lane_name} paused → {int(round(lane_weight_pct * 100))}% transferred to Top-20 this week")

    lines.append("")  # línea en blanco
    return "\n".join(lines)


def _summarize_rows(rows: List[RowT], max_lines: int = 20) -> List[str]:
    """
    Construye líneas por símbolo con señales resumidas.
    Intenta leer de scores/order/metrics de forma tolerante.
    """
    out = []
    for (sym, m, o, s, z) in rows[:max_lines]:
        score = getattr(s, "buy_score", None)
        vol_vs_avg = getattr(s, "vol_vs_avg", None) or getattr(o, "vol_vs_avg", None) or getattr(m, "vol_vs_avg", None)
        tbd = getattr(o, "taker_buy_dom", None) or getattr(s, "taker_buy_dom", None)
        ob_bid = getattr(o, "ob_imb_bid", None) or getattr(s, "ob_imb_bid", None)
        pos_sma = None
        try:
            if hasattr(m, "close") and hasattr(m, "sma200") and m.sma200 not in (None, 0):
                pos_sma = float(m.close) / float(m.sma200)
        except Exception:
            pos_sma = None

        line = (
            f"• {sym}  —  Score: {_fmt_num(score, 1)} | "
            f"Vol/Avg: {_fmt_num(vol_vs_avg, 2)} | "
            f"BuyDom: {_fmt_num(tbd, 2)} | "
            f"OB Bid: {_fmt_num(ob_bid, 2)} | "
            f"Px/SMA200: {_fmt_num(pos_sma, 3)}"
        )
        out.append(line)
    return out


def _top20_block(
    eligible_rows: List[RowT],
    allocation: Dict[str, Any],
    entry_triggers: Optional[Dict[str, Any]] = None,
) -> str:
    lines = []
    lines.append("─" * 31)
    lines.append("🧭 TOP 20 — Accumulation candidates")

    top20_alloc = allocation.get("top20", {}) if isinstance(allocation, dict) else {}
    budget_avail = top20_alloc.get("budget_total", 0.0)
    reserved = top20_alloc.get("reserved_next_week", 0.0)

    lines.append(f"💰 Budget available: {_fmt_money(budget_avail)}")
    if reserved and reserved > 0:
        lines.append(f"💵 Reserved for next week: {_fmt_money(reserved)}")

    # Candidatos
    if not eligible_rows:
        lines.append("")
        lines.append("No eligible coins this week.")
        lines.append("")
        return "\n".join(lines)

    # Mostrar candidatos recomendados (si allocation incluye por-coin, usa eso para los montos)
    per_coin = {}
    coin_allocs = top20_alloc.get("per_coin", []) if isinstance(top20_alloc.get("per_coin", []), list) else []
    for row in coin_allocs:
        try:
            sym = row.get("symbol")
            per_coin[sym] = float(row.get("budget", 0.0))
        except Exception:
            continue

    lines.append("")
    for (sym, m, o, s, z) in eligible_rows:
        score = getattr(s, "buy_score", None)
        vol_vs_avg = getattr(s, "vol_vs_avg", None) or getattr(o, "vol_vs_avg", None) or getattr(m, "vol_vs_avg", None)
        tbd = getattr(o, "taker_buy_dom", None) or getattr(s, "taker_buy_dom", None)
        ob_bid = getattr(o, "ob_imb_bid", None) or getattr(s, "ob_imb_bid", None)
        pos_sma = None
        try:
            if hasattr(m, "close") and hasattr(m, "sma200") and m.sma200 not in (None, 0):
                pos_sma = float(m.close) / float(m.sma200)
        except Exception:
            pos_sma = None

        budget_line = ""
        if sym in per_coin:
            budget_line = f"\n   💵 Invest: {_fmt_money(per_coin[sym])}"

        trigger_line = ""
        if entry_triggers and sym in entry_triggers:
            trig = entry_triggers[sym]
            # trig: EntryTrigger
            trigger_line = (
                f"\n   📌 Entry trigger: {_fmt_num(trig.trigger_price, 6)} "
                f"(min {_fmt_num(trig.lookback_min_price, 6)} + {trig.trigger_from_min_pct*100:.1f}%)"
                f"\n      ↳ {trig.reason}"
            )

        lines.append(
            f"✅ {sym} — Score: {_fmt_num(score, 1)} | "
            f"Vol/Avg: {_fmt_num(vol_vs_avg, 2)} | "
            f"BuyDom: {_fmt_num(tbd, 2)} | "
            f"OB Bid: {_fmt_num(ob_bid, 2)} | "
            f"Px/SMA200: {_fmt_num(pos_sma, 3)}"
            f"{budget_line}{trigger_line}"
        )

    # Fallback DCA (si existe)
    fb = top20_alloc.get("fallback", [])
    if isinstance(fb, list) and fb:
        lines.append("")
        lines.append("🔁 Fallback DCA (no signals):")
        for row in fb:
            sym = row.get("symbol")
            bud = row.get("budget", 0.0)
            lines.append(f"• {sym} → {_fmt_money(bud)}")

    lines.append("")
    return "\n".join(lines)


def _summary_block(lane_decisions: Dict[str, str], next_review_days: int = 7) -> str:
    # % por lane sólo informativo; podría no coincidir con asignación real si hubo transferencias
    btc_state = lane_decisions.get("BTC", "PAUSE")
    eth_state = lane_decisions.get("ETH", "PAUSE")
    # En el footer mantenemos un resumen simple como antes
    d1 = _today_utc() + dt.timedelta(days=next_review_days)
    return (
        "📊 Strategy summary\n"
        f"BTC: {'0%' if btc_state.upper()!='BUY' else 'active'} | "
        f"ETH: {'0%' if eth_state.upper()!='BUY' else 'active'} | "
        f"TOP 20: remainder\n"
        f"Next review: {d1}"
    )


# ---------------------------
# Formatter principal
# ---------------------------

def format_weekly_message(
    settings: Dict[str, Any],
    lane_decisions: Dict[str, str],
    allocation: Dict[str, Any],
    rows: List[RowT],
    eligible: List[RowT],
    entry_triggers: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Construye el mensaje completo para Telegram.
    """
    cfg_report = settings.get("report", {}) or {}
    show_transfers = bool(cfg_report.get("show_transfers", True))

    cfg_lanes = settings.get("lanes", {}) or {}
    btc_weight = float(_get(cfg_lanes, "btc", "weight", default=0.25) or 0.0)
    eth_weight = float(_get(cfg_lanes, "eth", "weight", default=0.15) or 0.0)
    top_weight = float(_get(cfg_lanes, "top20", "weight", default=0.60) or 0.0)

    btc_trail = float(_get(cfg_lanes, "btc", "trailing", default=0.038) or 0.038)
    eth_trail = float(_get(cfg_lanes, "eth", "trailing", default=0.050) or 0.050)
    top_trail = float(_get(cfg_lanes, "top20", "trailing_default", default=0.07) or 0.07)

    # Presupuesto total (suma lo detectado en allocation)
    total_budget = 0.0
    for lane_key in ("btc", "eth", "top20"):
        total_budget += float(_get(allocation, lane_key, "budget_total", default=0.0) or 0.0)

    parts: List[str] = []

    # Encabezado
    parts.append(_header(total_budget))

    # BTC / ETH
    parts.append(
        _lane_block("⚪", "BTC", lane_decisions, allocation, btc_trail, btc_weight, show_transfers)
    )
    parts.append(
        _lane_block("⚪", "ETH", lane_decisions, allocation, eth_trail, eth_weight, show_transfers)
    )

    # TOP 20
    # Filtra 'eligible' para mostrar sólo los recomendados (si ya viene así, no cambia nada)
    eligible_rows = eligible if eligible else []
    parts.append(
        _top20_block(eligible_rows, allocation, entry_triggers=entry_triggers)
    )

    # Footer resumen
    parts.append(_summary_block(lane_decisions))

    return "\n".join(parts)
