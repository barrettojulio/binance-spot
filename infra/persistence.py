import os, csv, datetime as dt

class Persistence:
    def __init__(self, base_dir="data"):
        self.base = base_dir
        os.makedirs(self.base, exist_ok=True)
        os.makedirs(f"{self.base}/snapshots", exist_ok=True)
        os.makedirs(f"{self.base}/logs", exist_ok=True)

    def export_snapshot(self, name, rows, eligible, allocation):
        ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        snap = f"{self.base}/snapshots/{name}_{ts}.csv"
        with open(snap, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["symbol","buy_score","zone","taker_buy_dom","ob_imb_bid","vol_last","vol_avg_12m"])
            for sym, metrics, order, scores, zone in rows:
                w.writerow([sym, f"{scores.buy_score:.2f}", zone, f"{order.taker_buy_dom:.2f}", f"{order.ob_imb_bid:.2f}", f"{metrics.quote_vol_last:.2f}", f"{metrics.quote_vol_avg_12m:.2f}"])
        elig_path = f"{self.base}/snapshots/eligible_{ts}.csv"
        with open(elig_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["symbol","buy_score","allocation_usdt"])
            for sym, sc, amt in eligible:
                w.writerow([sym, f"{sc:.2f}", f"{amt:.2f}"])
        alloc_path = f"{self.base}/snapshots/allocation_{ts}.csv"
        with open(alloc_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["btc_budget","eth_budget","top_budget","top_reserve"])
            w.writerow([allocation["btc_budget"], allocation["eth_budget"], allocation["top_budget"], allocation["top_reserve"]])
        return snap, elig_path, alloc_path
