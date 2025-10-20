# strategy/trailing.py
from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
import math


# ==============================
# Data classes
# ==============================

@dataclass
class EntryTrigger:
    """
    Representa el "gatillo" de compra basado en:
      - mínimo reciente (lookback)
      - porcentaje de rebote desde ese mínimo
      - validación de zona de valor (precio cerca de SMA200)
    """
    symbol: str
    lookback_min_price: float
    trigger_price: float
    trigger_from_min_pct: float
    near_sma_mult: float
    lookback_days: int
    reason: str


@dataclass
class ExitTrailingPlan:
    """
    Plan genérico de trailing para salida parcial.
    No ejecuta órdenes; sirve para formatear alertas/planes.
    """
    symbol: str
    lane: str                 # "BTC" | "ETH" | "TOP20"
    trailing_pct: float       # p. ej. 0.038 -> 3.8%
    partial_take_pct: float   # p. ej. 0.30  -> 30% de la posición


@dataclass
class ExitTrailingSnapshot:
    """
    Instantánea de niveles actuales del trailing dado un entry y el mayor
    precio alcanzado (highest_since_entry).
    """
    symbol: str
    lane: str
    trailing_pct: float
    partial_take_pct: float
    entry_price: float
    highest_price: float
    stop_price: float


# ==============================
# Helpers
# ==============================

def _min_over_lookback(closes: List[float], lookback_days: int) -> Optional[float]:
    """Devuelve el mínimo de cierres en los últimos `lookback_days` días."""
    if not closes or lookback_days <= 0 or len(closes) < lookback_days:
        return None
    window = closes[-lookback_days:]
    # Filtrar valores inválidos
    window = [x for x in window if isinstance(x, (int, float)) and x > 0]
    return min(window) if window else None


def _is_finite_pos(x: float) -> bool:
    try:
        return (x is not None) and math.isfinite(float(x)) and (float(x) > 0.0)
    except Exception:
        return False


# ==============================
# Trailing de COMPRA (Entry Trigger)
# ==============================

def build_entry_trigger(
    symbol: str,
    closes: List[float],
    sma200: float,
    near_sma_mult: float,
    lookback_days: int,
    trigger_from_min_pct: float,
) -> Optional[EntryTrigger]:
    """
    Construye un gatillo de compra si:
      1) Hay datos suficientes de `closes`.
      2) El último cierre está en "zona de valor": last_close ≤ near_sma_mult * sma200
      3) Existe mínimo reciente (lookback) válido.
      4) El precio-gatillo = min_lookback * (1 + trigger_from_min_pct) es coherente.

    No ejecuta órdenes; devuelve la info que el formatter usa para Telegram.
    """
    if not closes or len(closes) < max(lookback_days, 5):
        return None
    if not _is_finite_pos(sma200):
        return None
    last_close = closes[-1]
    if not _is_finite_pos(last_close):
        return None

    # (1) Validar zona de valor
    max_allowed = near_sma_mult * sma200
    if last_close > max_allowed:
        return None

    # (2) Hallar mínimo reciente
    lb_min = _min_over_lookback(closes, lookback_days)
    if not _is_finite_pos(lb_min):
        return None

    # (3) Calcular precio gatillo (rebote)
    trigger_price = lb_min * (1.0 + trigger_from_min_pct)
    if not _is_finite_pos(trigger_price):
        return None

    reason = (
        f"Near SMA200 (≤{near_sma_mult:.2f}×SMA200) + "
        f"rebound from {lookback_days}d-min by {trigger_from_min_pct*100:.1f}%"
    )
    return EntryTrigger(
        symbol=symbol,
        lookback_min_price=lb_min,
        trigger_price=trigger_price,
        trigger_from_min_pct=trigger_from_min_pct,
        near_sma_mult=near_sma_mult,
        lookback_days=lookback_days,
        reason=reason,
    )


# ==============================
# Trailing de VENTA PARCIAL (Plan & Cálculo de stop)
# ==============================

def build_exit_trailing_plan(
    symbol: str,
    lane: str,
    exit_cfg: Dict[str, float],
    default_partial_take_pct: Optional[float] = None,
) -> Optional[ExitTrailingPlan]:
    """
    Crea un plan de trailing de salida parcial por carril usando `exit_cfg` del settings:

      exit_trailing:
        btc: 0.038
        eth: 0.050
        top20_default: 0.07
        partial_take_pct: 0.30

    lane: "BTC" | "ETH" | "TOP20"
    """
    if not lane:
        return None
    lane_u = lane.upper()

    partial_take = exit_cfg.get("partial_take_pct", default_partial_take_pct or 0.30)

    if lane_u == "BTC":
        trailing_pct = float(exit_cfg.get("btc", 0.038))
    elif lane_u == "ETH":
        trailing_pct = float(exit_cfg.get("eth", 0.050))
    else:
        # TOP-20 u otros caen aquí
        trailing_pct = float(exit_cfg.get("top20_default", 0.07))

    # Validaciones básicas
    if trailing_pct <= 0 or trailing_pct >= 0.50:  # trailing > 50% carece de sentido aquí
        return None
    if partial_take <= 0 or partial_take >= 1.0:
        return None

    return ExitTrailingPlan(
        symbol=symbol,
        lane=lane_u,
        trailing_pct=trailing_pct,
        partial_take_pct=partial_take,
    )


def compute_trailing_stop(
    entry_price: float,
    highest_since_entry: float,
    trailing_pct: float,
) -> Optional[float]:
    """
    Calcula el stop dinámico dado:
      - `entry_price`: precio de entrada.
      - `highest_since_entry`: el mayor precio visto desde la entrada.
      - `trailing_pct`: porcentaje de trailing (ej. 0.07 = 7%).

    Fórmula clásica:
      stop = highest_since_entry * (1 - trailing_pct)

    Devuelve None si los números no son válidos.
    """
    if not (_is_finite_pos(entry_price) and _is_finite_pos(highest_since_entry)):
        return None
    if trailing_pct <= 0 or trailing_pct >= 0.50:
        return None
    if highest_since_entry < entry_price * 0.5:
        # sanity check para evitar niveles absurdos (datos malos)
        return None

    stop = highest_since_entry * (1.0 - trailing_pct)
    return stop if _is_finite_pos(stop) else None


def snapshot_exit_trailing(
    symbol: str,
    lane: str,
    entry_price: float,
    highest_since_entry: float,
    exit_cfg: Dict[str, float],
) -> Optional[ExitTrailingSnapshot]:
    """
    Crea una instantánea de salida parcial con el stop actual.
    Útil para incluir una línea clara en el mensaje de Telegram:
      - trailing %
      - partial_take %
      - nivel de stop dinámico
    """
    plan = build_exit_trailing_plan(symbol, lane, exit_cfg)
    if not plan:
        return None

    stop = compute_trailing_stop(entry_price, highest_since_entry, plan.trailing_pct)
    if not _is_finite_pos(stop):
        return None

    return ExitTrailingSnapshot(
        symbol=symbol,
        lane=plan.lane,
        trailing_pct=plan.trailing_pct,
        partial_take_pct=plan.partial_take_pct,
        entry_price=entry_price,
        highest_price=highest_since_entry,
        stop_price=stop,
    )
