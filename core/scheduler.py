import os
from pathlib import Path
import yaml
from dotenv import load_dotenv

from core.pipeline import Pipeline


def _project_root() -> Path:
    """
    Devuelve la carpeta raíz del proyecto (donde vive cli.py).
    Este archivo está en core/, así que subimos 1 nivel.
    """
    return Path(__file__).resolve().parents[1]


def _load_settings(settings_path: str) -> dict:
    """
    Lee settings.yaml, carga .env desde la raíz del proyecto, y sobrescribe
    las claves del bloque `api` con las presentes en el entorno (si existen).
    """
    # 1) Cargar settings.yaml
    with open(settings_path, "r", encoding="utf-8") as f:
        settings = yaml.safe_load(f) or {}

    # 2) Cargar .env explícitamente desde la raíz del proyecto (independiente del CWD)
    env_path = _project_root() / ".env"
    load_dotenv(dotenv_path=env_path, override=True)

    # 3) Sobrescribir API keys/token desde variables de entorno (si existen)
    env_map = {
        "cmc_key": os.getenv("CMC_API_KEY"),
        "telegram_token": os.getenv("TELEGRAM_BOT_TOKEN"),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID"),
        # Opcionales (si algún día activas trading privado):
        "binance_key": os.getenv("BINANCE_API_KEY"),
        "binance_secret": os.getenv("BINANCE_API_SECRET"),
    }
    api = settings.setdefault("api", {})
    for k, v in env_map.items():
        if v:
            api[k] = v

    # 4) (Opcional) presupuesto por defecto desde .env si no está en settings
    #    DEFAULT_BUDGET se usa en run_weekly cuando no pasas --budget
    run_cfg = settings.setdefault("run", {})
    if not run_cfg.get("default_budget"):
        try:
            env_default_budget = float(os.getenv("DEFAULT_BUDGET", "0") or 0)
            if env_default_budget > 0:
                run_cfg["default_budget"] = env_default_budget
        except ValueError:
            pass

    # Logs mínimos para saber si tomó variables del entorno (sin exponerlas):
    print(f"[ENV] Loaded .env from: {env_path} | CMC: {bool(api.get('cmc_key'))} | TG: {bool(api.get('telegram_token'))}")

    return settings


def run_refresh_cmc(settings_path: str):
    """
    Refresca manualmente el Top-200 de CoinMarketCap y actualiza el cache local.
    Usa CMC_API_KEY desde .env (o desde settings.yaml si ahí está definida).
    """
    settings = _load_settings(settings_path)
    pl = Pipeline(settings)
    pl.refresh_cmc_top200()
    print("[CMC] Top-200 cache refreshed.")


def run_weekly(settings_path: str, total_budget: float = 0.0):
    """
    Ejecuta el análisis semanal end-to-end.
    - Si no se pasa --budget, usa run.default_budget de settings.yaml o DEFAULT_BUDGET del .env.
    """
    settings = _load_settings(settings_path)

    # Presupuesto por defecto si no se pasó --budget
    if not total_budget:
        try:
            total_budget = float(
                settings.get("run", {}).get("default_budget", 0) or os.getenv("DEFAULT_BUDGET", "0") or 0
            )
        except ValueError:
            total_budget = 0.0

    pl = Pipeline(settings)
    pl.run_weekly(total_budget=total_budget)
    print("[WEEKLY] Run finished.")
