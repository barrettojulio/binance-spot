import pandas as pd
from core.types import SymbolMetrics

COLS = ["open_time","open","high","low","close","volume","close_time","quote_vol","trades","taker_buy_base","taker_buy_quote","ignore"]

def _to_df(klines):
    df = pd.DataFrame(klines, columns=COLS)
    for c in ["open","high","low","close","volume","quote_vol","taker_buy_base","taker_buy_quote"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def compute_indicators_12m(binance_client, symbol) -> SymbolMetrics:
    k = binance_client.klines_1d_365(symbol)
    if not k or len(k) < 200:
        return SymbolMetrics(symbol,0,0,0,999,0,0,0,0)
    df = _to_df(k)
    close = df["close"].iloc[-1]
    sma50 = df["close"].rolling(50).mean().iloc[-1]
    sma200 = df["close"].rolling(200).mean().iloc[-1]
    high_12m = df["high"].max()
    low_12m = df["low"].min()
    quote_vol_avg_12m = df["quote_vol"].rolling(200).mean().iloc[-1]
    quote_vol_last = df["quote_vol"].iloc[-1]
    prev_close = df["close"].shift(1)
    tr = pd.concat([(df["high"]-df["low"]).abs(), (df["high"]-prev_close).abs(), (df["low"]-prev_close).abs()], axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean().iloc[-1]
    atr_pct = float((atr14/close)*100) if close>0 else 999
    return SymbolMetrics(symbol=float(""), close=float(close), sma50=float(sma50), sma200=float(sma200), atr_pct=float(atr_pct), quote_vol_last=float(quote_vol_last), quote_vol_avg_12m=float(quote_vol_avg_12m), high_12m=float(high_12m), low_12m=float(low_12m))
