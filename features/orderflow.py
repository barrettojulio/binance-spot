from core.types import OrderFlow

def compute_orderflow(binance_client, symbol, hours=24, ob_levels=20) -> OrderFlow:
    trades = binance_client.agg_trades_window(symbol, hours=hours, max_pages=6)
    total_buy = 0.0; total_sell = 0.0
    for t in trades:
        price = float(t["p"]); qty = float(t["q"]); notional = price*qty
        if t["m"]: total_sell += notional
        else: total_buy += notional
    cvd = total_buy - total_sell
    dom = total_buy / max(1e-9, (total_buy + total_sell))
    depth = binance_client.orderbook(symbol, levels=ob_levels)
    def _sum(side):
        acc = 0.0
        for p,q in side[:ob_levels]: acc += float(p)*float(q)
        return acc
    bids = depth.get("bids", []); asks = depth.get("asks", [])
    bid_not = _sum(bids); ask_not = _sum(asks); tot = bid_not+ask_not
    imb = (bid_not/tot) if tot>0 else 0.5
    return OrderFlow(cvd_notional=float(cvd), taker_buy_dom=float(dom), ob_imb_bid=float(imb))
