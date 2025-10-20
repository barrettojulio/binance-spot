from dataclasses import dataclass

@dataclass
class SymbolMetrics:
    symbol: str
    close: float
    sma50: float
    sma200: float
    atr_pct: float
    quote_vol_last: float
    quote_vol_avg_12m: float
    high_12m: float
    low_12m: float

@dataclass
class OrderFlow:
    cvd_notional: float
    taker_buy_dom: float
    ob_imb_bid: float

@dataclass
class QualityFlags:
    liquidity_ok: bool
    atr_ok: bool
    tradable: bool

@dataclass
class Scores:
    buy_score: float
    sell_score: float
    zone: str
