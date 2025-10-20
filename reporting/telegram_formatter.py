from datetime import datetime, timedelta
from strategy.trailing import trailing_for_lane

def format_weekly_message(settings, lane_decisions, allocation, rows, eligible) -> str:
    today = datetime.utcnow().date(); next_week = today + timedelta(days=7)
    lines = []
    lines.append(f"📅 Week: {today} – {next_week}")
    total_budget = allocation["btc_budget"] + allocation["eth_budget"] + allocation["top_budget"]
    lines.append(f"💰 Total budget: ${total_budget:,.2f} USDT\n")
    lines.append("───────────────────────────────")
    # BTC
    btc_on = (lane_decisions.get("BTC") == "BUY")
    btc_tr = trailing_for_lane(settings, "BTC")
    lines.append(f"{'🟢' if btc_on else '⚪'} BTC/USDT — {'Buy confirmed' if btc_on else 'Neutral / Pause'}")
    lines.append(f"Trailing Stop: {btc_tr:.1f} %")
    lines.append(f"💰 Budget: ${allocation['btc_budget']:,.2f} (25 %)\n")
    lines.append("───────────────────────────────")
    # ETH
    eth_on = (lane_decisions.get("ETH") == "BUY")
    eth_tr = trailing_for_lane(settings, "ETH")
    lines.append(f"{'🟢' if eth_on else '⚪'} ETH/USDT — {'Buy confirmed' if eth_on else 'Neutral / Pause'}")
    lines.append(f"Trailing Stop: {eth_tr:.1f} %")
    lines.append(f"💰 Budget: ${allocation['eth_budget']:,.2f} (15 %)")
    if not eth_on: lines.append("↪ ETH paused → 15% transferred to Top-20 this week")
    if not btc_on: lines.append("↪ BTC paused → 25% transferred to Top-20 this week")
    lines.append("\n───────────────────────────────")
    # TOP-20
    lines.append("🧭 TOP 20 — Accumulation candidates")
    lines.append(f"💰 Budget available: ${allocation['top_budget']:,.2f}")
    if eligible: lines.append(f"Eligible: {len(eligible)} / 20")
    if allocation["top_reserve"]>0: lines.append(f"💵 Reserved for next week: ${allocation['top_reserve']:,.2f}")
    lines.append("")
    if allocation["top_allocations"]:
        for sym, amt in allocation["top_allocations"][:20]:
            score = next((sc for s, sc in eligible if s==sym), 0.0)
            lines.append(f"🟢 {sym} — Score {score:.2f} | Trailing 7% | 💰 ${amt:,.2f}")
    else:
        lines.append("No eligible coins this week.")
    lines.append("")
    lines.append("📊 Strategy summary")
    lines.append(f"BTC: {'25%' if btc_on else '0%'} | ETH: {'15%' if eth_on else '0%'} | TOP 20: remainder")
    lines.append(f"Next review: {next_week}")
    return "\n".join(lines)
