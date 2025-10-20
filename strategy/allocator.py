def allocate_budgets(settings, lane_decisions, total_budget: float, eligible):
    lanes_cfg = settings.get("lanes", {})
    w_btc = float(lanes_cfg.get("btc", {}).get("weight", 0.25))
    w_eth = float(lanes_cfg.get("eth", {}).get("weight", 0.15))
    w_top = float(lanes_cfg.get("top20", {}).get("weight", 0.60))
    btc_on = lane_decisions.get("BTC") == "BUY"
    eth_on = lane_decisions.get("ETH") == "BUY"
    btc_budget = total_budget * w_btc if btc_on else 0.0
    eth_budget = total_budget * w_eth if eth_on else 0.0
    transferred = (0 if btc_on else total_budget * w_btc) + (0 if eth_on else total_budget * w_eth)
    top_budget = total_budget * w_top + transferred
    amounts = []
    reserve = float(top_budget)
    if eligible:
        scores = [max(0.0, s) for _, s in eligible]
        tot = sum(scores)
        if tot <= 0:
            per = round(top_budget / len(eligible), 2)
            for sym, _ in eligible: amounts.append((sym, per))
            reserve = round(top_budget - per*len(eligible), 2)
        else:
            remaining = round(top_budget, 2)
            for sym, sc in eligible[:-1]:
                amt = round(top_budget * (sc/tot), 2)
                amounts.append((sym, amt))
                remaining = round(remaining - amt, 2)
            amounts.append((eligible[-1][0], remaining))
            reserve = 0.0
    return {"btc_budget": round(btc_budget, 2), "eth_budget": round(eth_budget, 2), "top_budget": round(top_budget, 2), "top_allocations": amounts, "top_reserve": round(reserve, 2)}
