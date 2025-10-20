import time
import requests
from typing import List, Dict

BINANCE_BASE = "https://api.binance.com"


class BinanceClient:
    """
    Cliente ligero para endpoints PÚBLICOS de Binance:
      - exchangeInfo (lista de símbolos)
      - klines (1d/365)
      - aggTrades (ventana de horas)
      - depth (order book)

    NOTA: No requiere API key para estos endpoints.
    """

    def __init__(self, settings: dict):
        self.settings = settings

    # ---------------------------
    # Helpers HTTP
    # ---------------------------
    def _get(self, path: str, params: dict | None = None, timeout: int = 30):
        """GET simple con manejo de errores básico."""
        url = f"{BINANCE_BASE}{path}"
        r = requests.get(url, params=params or {}, timeout=timeout)
        r.raise_for_status()
        return r.json()

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
        # Normaliza CMC a mayúsculas por seguridad
        cmc_set = {str(s).upper() for s in (top200_symbols or [])}

        # Lista completa de pares USDT en Binance
        all_usdt = self.list_usdt_symbols()

        # Filtra por base presente en CMC
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
        Velas diarias (máx 365). Columnas:
        [open_time, open, high, low, close, volume, close_time,
         quote_asset_volume, number_of_trades, taker_buy_base, taker_buy_quote, ignore]
        """
        params = {"symbol": symbol, "interval": "1d", "limit": 365}
        return self._get("/api/v3/klines", params=params)

    def agg_trades_window(self, symbol: str, hours: int = 24, max_pages: int = 6):
        """
        Agregados de trades en una ventana temporal (hasta ~6k elementos con paginado simple).
        Útil para estimar CVD y dominancia de compras/ventas.
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
            # avanzar la ventana hacia atrás (usamos el timestamp del PRIMER trade devuelto)
            last_end = data[0]["T"]
            if len(data) < 1000:
                break
        return merged

    def orderbook(self, symbol: str, levels: int = 20):
        """
        Libro de órdenes (depth). Devuelve bids/asks hasta 'levels' (límite de Binance: 5000).
        """
        params = {"symbol": symbol, "limit": min(int(levels), 5000)}
        return self._get("/api/v3/depth", params=params)
