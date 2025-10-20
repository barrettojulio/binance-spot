import time
import requests
from typing import List, Dict, Optional

BINANCE_BASE = "https://api.binance.com"


class BinanceClient:
    """
    Endpoints PÚBLICOS de Binance (sin API key):
      - exchangeInfo
      - klines (1d/365)
      - aggTrades (ventana horas)
      - depth (order book)

    Incluye reintentos con backoff exponencial y headers para reducir 429.
    """

    def __init__(self, settings: dict):
        self.settings = settings
        run = settings.get("run", {}) or {}
        # Permite ajustar tiempo de espera y reintentos desde settings si quieres
        self.http_timeout = int(run.get("http_timeout_seconds", 30))
        self.max_retries = int(run.get("http_max_retries", 5))
        self.backoff_base = float(run.get("http_backoff_base", 0.5))

    # ---------------------------
    # Helpers HTTP con retry/backoff
    # ---------------------------
    def _get(
        self,
        path: str,
        params: Optional[dict] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        backoff_base: Optional[float] = None,
    ):
        url = f"{BINANCE_BASE}{path}"
        headers = {
            "Accept": "application/json",
            "User-Agent": "InstitutionalSpotRadar/1.0 (+https://github.com/barrettojulio/binance-spot)",
        }
        if timeout is None:
            timeout = self.http_timeout
        if max_retries is None:
            max_retries = self.max_retries
        if backoff_base is None:
            backoff_base = self.backoff_base

        last_err = None
        for attempt in range(max_retries):
            try:
                r = requests.get(url, params=params or {}, timeout=timeout, headers=headers)
                # Si hay rate limit o ban temporal, forzamos retry
                if r.status_code in (418, 429):
                    raise requests.HTTPError(f"{r.status_code} {r.reason}")
                r.raise_for_status()
                return r.json()
            except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as e:
                last_err = e
                sleep_s = backoff_base * (2 ** attempt)  # backoff exponencial
                time.sleep(sleep_s)
                continue
        # agotamos reintentos
        raise last_err if last_err else RuntimeError("Unknown error on GET")

    # ---------------------------
    # Universo / Símbolos
    # ---------------------------
    def list_usdt_symbols(self) -> List[Dict[str, str]]:
        """
        Devuelve TODOS los símbolos USDT en estado TRADING.
        Formato: [{"symbol": "BTCUSDT", "base": "BTC"}, ...]
        """
        ex = self._get("/api/v3/exchangeInfo")
        out = []
        for s in ex.get("symbols", []):
            if s.get("status") != "TRADING":
                continue
            if s.get("quoteAsset") != "USDT":
                continue
            out.append({"symbol": s["symbol"], "base": s["baseAsset"]})
        return out

    def get_usdt_symbols_intersection(self, top200_symbols: List[str]) -> List[str]:
        """
        Intersección entre:
          - baseAssets del Top-200 (CoinMarketCap)
          - pares USDT TRADING en Binance
        Retorna la lista de símbolos Binance (ej.: ["BTCUSDT","ETHUSDT",...]).
        """
        cmc_set = {str(s).upper() for s in (top200_symbols or [])}
        all_usdt = self.list_usdt_symbols()
        out = []
        for row in all_usdt:
            base = (row.get("base") or "").upper()
            if base in cmc_set:
                out.append(row["symbol"])
        return out

    # ---------------------------
    # Datos de mercado
    # ---------------------------
    def klines_1d_365(self, symbol: str):
        """
        Velas diarias (máx 365). Valida que la respuesta no venga vacía.
        """
        params = {"symbol": symbol, "interval": "1d", "limit": 365}
        data = self._get("/api/v3/klines", params=params)
        if not isinstance(data, list) or len(data) == 0:
            raise RuntimeError(f"No klines returned for {symbol}")
        return data

    def agg_trades_window(self, symbol: str, hours: int = 24, max_pages: int = 6):
        """
        Agregados de trades en una ventana temporal.
        """
        end = int(time.time() * 1000)
        start = end - hours * 3600 * 1000
        merged = []
        last_end = end
        for _ in range(max_pages):
            params = {"symbol": symbol, "limit": 1000, "startTime": start, "endTime": last_end}
            data = self._get("/api/v3/aggTrades", params=params)
            if not data:
                break
            merged.extend(data)
            # avanzar la ventana hacia atrás
            last_end = data[0]["T"]
            if len(data) < 1000:
                break
        return merged

    def orderbook(self, symbol: str, levels: int = 20):
        """
        Libro de órdenes (depth).
        """
        params = {"symbol": symbol, "limit": min(int(levels), 5000)}
        return self._get("/api/v3/depth", params=params)
