# core/scheduler.py
from __future__ import annotations

import os
import sys
import yaml
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from core.pipeline import Pipeline


# -----------------------------
# Utilidades de configuración
# -----------------------------

def _load_file_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _safe_load_yaml(path: str) -> Dict[str, Any]:
    try:
        text = _load_file_text(path)
    except FileNotFoundError:
        raise FileNotFoundError(f"[ERROR] settings file not found: {path}")
    try:
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            raise ValueError("settings root must be a mapping")
        return data
    except yaml.YAMLError as e:
        raise RuntimeError(f"[ERROR] YAML parse error in {path}: {e}")


def _bool_from_env(value: Optional[str]) -> Optional[bool]:
    if value is None:
        return None
    v = value.strip().lower()
    if v in ("1", "true", "yes", "on"):
        return True
    if v in ("0", "false", "no", "off"):
        return False
    return None


def _merge_env_into_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sobrescribe credenciales y banderas desde .env si están presentes.
    Variables soportadas:
      - CMC_API_KEY
      - TELEGRAM_BOT_TOKEN
      - TELEGRAM_CHAT_ID
      - SEND_TELEGRAM (opcional: fuerza envío)
      - DEFAULT_BUDGET (opcional)
    """
    api = settings.setdefault("api", {})
    run = settings.setdefault("run", {})

    cmc_env = os.getenv("CMC_API_KEY")
    tg_token_env = os.getenv("TELEGRAM_BOT_TOKEN")
    tg_chat_env = os.getenv("TELEGRAM_CHAT_ID")
    send_tg_env = _bool_from_env(os.getenv("SEND_TELEGRAM"))
    default_budget_env = os.getenv("DEFAULT_BUDGET")

    if cmc_env:
        api["cmc_key"] = cmc_env
    if tg_token_env:
        api["telegram_token"] = tg_token_env
    if tg_chat_env:
        api["telegram_chat_id"] = tg_chat_env
    if send_tg_env is not None:
        run["send_telegram"] = bool(send_tg_env)
    if default_budget_env:
        try:
            run["default_budget"] = float(default_budget_env)
        except ValueError:
            pass

    return settings


def _env_banner(settings_path: str, settings: Dict[str, Any]) -> None:
    env_loaded_from = None
    # dotenv devuelve True/False; no da la ruta. La inferimos si existe .env en cwd.
    # Preferimos mostrar una ruta amigable si el archivo existe.
    cwd_env = os.path.join(os.getcwd(), ".env")
    if os.path.exists(cwd_env):
        env_loaded_from = cwd_env
    else:
        # otras ubicaciones comunes (no garantizado)
        possible = [".env", os.path.join(os.path.dirname(settings_path), ".env")]
        for p in possible:
            if os.path.exists(p):
                env_loaded_from = p
                break

    api = settings.get("api", {}) or {}
    has_cmc = bool(api.get("cmc_key"))
    has_tg = bool(api.get("telegram_token")) and bool(api.get("telegram_chat_id"))
    print(
        f"[ENV] Loaded .env from: {env_loaded_from or '(not found)'} | "
        f"CMC: {str(has_cmc)} | TG: {str(has_tg)}"
    )


def _normalize_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    # Aseguramos estructuras y defaults mínimos
    settings.setdefault("api", {})
    run = settings.setdefault("run", {})
    run.setdefault("cvd_hours", 24)
    run.setdefault("ob_levels", 20)
    run.setdefault("request_delay_seconds_phase1", 0.50)
    run.setdefault("request_delay_seconds", 0.50)
    run.setdefault("http_timeout_seconds", 30)
    run.setdefault("http_max_retries", 5)
    run.setdefault("http_backoff_base", 0.5)
    return settings


def _load_settings(settings_path: str) -> Dict[str, Any]:
    # 1) YAML
    settings = _safe_load_yaml(settings_path)
    # 2) .env (si existe)
    load_dotenv()  # no lanza excepción si no hay .env
    # 3) Fusionar env → settings
    settings = _merge_env_into_settings(settings)
    # 4) Normalizar
    settings = _normalize_settings(settings)
    # 5) Banner informativo
    _env_banner(settings_path, settings)
    return settings


# -----------------------------
# Runners públicos
# -----------------------------

def run_refresh_cmc(settings_path: str) -> None:
    """
    Refresca el caché del Top-200 de CMC (manual).
    """
    settings = _load_settings(settings_path)
    pipeline = Pipeline(settings)
    pipeline.refresh_cmc_top200()


def run_weekly(settings_path: str, total_budget: Optional[float] = None) -> None:
    """
    Ejecuta el análisis semanal con presupuesto total en USDT.
    Si total_budget es None, usa run.default_budget del YAML (si existe),
    en caso contrario 0.0 (con warning).
    """
    settings = _load_settings(settings_path)

    run_cfg = settings.get("run", {}) or {}
    if total_budget is None:
        total_budget = run_cfg.get("default_budget", 0.0)

    try:
        total_budget = float(total_budget)
    except Exception:
        total_budget = 0.0

    if total_budget <= 0:
        print("[WARN] total_budget <= 0. "
              "Using 0 USDT. Pass --budget in CLI or define run.default_budget in settings.")

    pipeline = Pipeline(settings)
    pipeline.run_weekly(total_budget=total_budget)
