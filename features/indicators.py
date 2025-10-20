# features/indicators.py
from dataclasses import dataclass
from typing import List, Tuple, Optional
import math

@dataclass
class SymbolMetrics:
    symbol: str
    close: float
    sma50: float
    sma200: float
    atr_pct: float
    quote_vol_last: float
    quote_vol_avg_12m: float
    # puedes añadir campos extra si los usas en filtros o scoring


def safe_float(x) -> Optional[float]:
    try:
        if x is None: 
            return None
        s = str(x).strip()
        if s == "":
            return None
        return float(s)
    except Exception:
        return None


def _true_range(h: float, l: float, prev_close: float) -> float:
    return max(h - l, abs(h - prev_close), abs(l - prev_close))


def _sma(arr: List[float], window: int) -> List[Optional[float]]:
    out = [None] * len(arr)
    if window <= 0 or len(arr) < window:
        return out
    s = sum(arr[:window])
    out[window - 1] = s / window
    for i in range(window, len(arr)):
        s += arr[i] - arr[i - window]
        out[i] = s / window
    return out


def compute_indicators_12m(binance_client, symbol: str) -> SymbolMetrics:
    """
    Lee klines 1D máx 365, filtra filas inválidas, y calcula:
      - close, SMA50, SMA200
      - ATR(14) en %, usando True Range clásico
      - quote_vol_last y quote_vol_avg_12m (promedio de la ventana válida)
    Lanza ValueError con explicación si no hay datos suficientes.
    """

    raw = binance_client.klines_1d_365(symbol)
    if not isinstance(raw, list) or len(raw) == 0:
        raise ValueError(f"no klines data (symbol={symbol})")

    # Estructura esperada por Binance:
    # [0] open_time, [1] open, [2] high, [3] low, [4] close, [5] volume,
    # [6] close_time, [7] quote_asset_volume, [8] number_of_trades,
    # [9] taker_buy_base, [10] taker_buy_quote, [11] ignore

    # Convertimos y filtramos velas inválidas (cualquier campo crítico None)
    highs, lows, closes, qvols = [], [], [], []
    for row in raw:
        if not isinstance(row, (list, tuple)) or len(row) < 12:
            continue
        o = safe_float(row[1])
        h = safe_float(row[2])
        l = safe_float(row[3])
        c = safe_float(row[4])
        qv = safe_float(row[7])  # quote asset volume

        # Campos críticos: high, low, close y quote vol.
        if h is None or l is None or c is None or qv is None:
            # descartamos esta vela por valores vacíos o inválidos
            continue

        highs.append(h)
        lows.append(l)
        closes.append(c)
        qvols.append(qv)

    n = len(closes)
    # Necesitamos al menos 200 velas para SMA200 y algo de margen para ATR14
    if n < 220:
        raise ValueError(f"not enough valid klines for SMA200/ATR (have={n}, need>=220) (symbol={symbol})")

    # SMA50 / SMA200
    sma50_series = _sma(closes, 50)
    sma200_series = _sma(closes, 200)
    sma50 = sma50_series[-1]
    sma200 = sma200_series[-1]
    if sma50 is None or sma200 is None or sma200 == 0:
        raise ValueError(f"invalid SMA values (sma50={sma50}, sma200={sma200}) (symbol={symbol})")

    # ATR(14)
    trs = []
    for i in range(1, n):
        tr = _true_range(highs[i], lows[i], closes[i - 1])
        trs.append(tr)
    if len(trs) < 14:
        raise ValueError(f"not enough TR samples for ATR14 (have={len(trs)}) (symbol={symbol})")
    atr14_series = _sma(trs, 14)
    atr14 = atr14_series[-1]
    if atr14 is None or closes[-1] == 0:
        raise ValueError(f"invalid ATR14 or close=0 (atr14={atr14}, close={closes[-1]}) (symbol={symbol})")
    atr_pct = (atr14 / closes[-1]) * 100.0

    # Volumen en USD (quote) — último y promedio en la ventana válida
    quote_vol_last = qvols[-1]
    quote_vol_avg_12m = sum(qvols) / max(1, len(qvols))

    return SymbolMetrics(
        symbol=symbol,
        close=closes[-1],
        sma50=sma50,
        sma200=sma200,
        atr_pct=atr_pct,
        quote_vol_last=quote_vol_last,
        quote_vol_avg_12m=quote_vol_avg_12m,
    )
