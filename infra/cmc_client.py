import os
import json
import requests
from datetime import datetime
from typing import List, Dict

class CMCClient:
    """
    Cliente para CoinMarketCap (listings/latest).
    - Guarda un cache local en data/cache_cmc.json
    - Devuelve la lista de símbolos del Top-200 en mayúsculas
    """

    def __init__(self, settings: Dict):
        self.api_key = (settings.get("api", {}) or {}).get("cmc_key", "")
        self.cache_path = "data/cache_cmc.json"

    def refresh_top200_cache(self):
        """
        Descarga los primeros 250 por market cap, ordena por cmc_rank
        y guarda solo los 200 primeros. Normaliza símbolos a MAYÚSCULAS.
        """
        if not self.api_key:
            raise RuntimeError("CMC API key missing in config.")

        url = "https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest"
        params = {"start": 1, "limit": 250, "convert": "USD", "sort": "market_cap"}
        headers = {"X-CMC_PRO_API_KEY": self.api_key}

        r = requests.get(url, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json().get("data", [])

        # Mapear y normalizar
        rows = []
        for x in data:
            cmc_rank = x.get("cmc_rank")  # CMC usa 'cmc_rank' en la respuesta
            symbol = (x.get("symbol") or "").upper().strip()
            name = x.get("name") or ""
            if not symbol:
                continue
            rows.append({"rank": cmc_rank, "symbol": symbol, "name": name})

        # Ordenar por rank y tomar 200
        rows = sorted(rows, key=lambda d: (d["rank"] if d["rank"] is not None else 999999))[:200]

        # Quitar duplicados por símbolo manteniendo el primero (mejor rank)
        seen = set()
        top = []
        for r in rows:
            if r["symbol"] in seen:
                continue
            seen.add(r["symbol"])
            top.append(r)

        cache = {
            "refreshed_at": datetime.utcnow().isoformat(),
            "top200": top,  # [{rank, symbol, name}, ...]
        }
        os.makedirs("data", exist_ok=True)
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)

    def load_top200_cache(self) -> List[str]:
        """
        Carga el cache y devuelve SOLO la lista de símbolos en mayúsculas.
        """
        if not os.path.exists(self.cache_path):
            raise RuntimeError(
                "CMC cache not found. Run:\n"
                "  python cli.py --refresh-cmc --settings config/settings.yaml"
            )
        with open(self.cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        symbols = []
        for x in data.get("top200", []):
            # Por si alguien editó el JSON a mano:
            sym = (x.get("symbol") or "").upper().strip()
            if sym:
                symbols.append(sym)

        # Desduplicar de nuevo por seguridad
        symbols = list(dict.fromkeys(symbols))

        return symbols
