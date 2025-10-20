# core/pipeline.py
import time
import os
import csv
import datetime as dt

from infra.persistence import Persistence
from infra.cmc_client import CMCClient
from infra.binance_client import BinanceClient

from features.indicators import compute_indicators_12m
from features.orderflow import compute_orderflow
from features.filters import pass_quality_filters

from scoring.buy_model import compute_buy_score
from scoring.thresholds import classify_zone

from strategy.selector import select_top20_eligible
from strategy.lanes import decide_lanes
from strategy.allocator import allocate_budgets
from strategy.trailing import build_entry_trigger  # ← Entry triggers (compra)

from reporting.telegram_formatter import format_weekly_message
from reporting.exports import export_weekly
from reporting.telegram_sender import TelegramSender

from reporting.diagnostics import (
    export_diagnostics,          # CSV compacto (evaluados)
    export_diagnostics_full,     # CSV completo (incluye filtrados y excepciones)
    _reason_and_flags,           # helper para checks de señal
)


class Pipeline:
    def __init__(self, settings):
        self.settings = settings
        self.persistence = Persistence(base_dir="data")
        self.cmc = CMCClient(settings)
        self.binance = BinanceClient(settings)
        self.tg = TelegramSender(settings)

    def refresh_cmc_top200(self):
        self.cmc.refresh_top200_cache()

    # ---------- Utilidad: exporta auditoría de universo ----------
    def _export_universe_audit(self, top200_symbols, all_usdt):
        """
        Exporta un CSV con el universo observado: bases USDT en Binance,
        si están en el Top-200 de CMC y qué símbolos USDT tienen.
        """
        os.makedirs("data/snapshots", exist_ok=True)
        ts = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        universe_csv = f"data/snapshots/universe_{ts}.csv"

        cmc_set = {str(s).upper() for s in (top200_symbols or [])}
        by_base = {}
        for r in all_usdt:
            base = r.get("base")
            by_base.setdefault(base, []).append(r.get("symbol"))

        with open(universe_csv, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["base", "has_usdt_pair_on_binance", "is_in_cmc_top200", "binance_symbols_joined"])
            # Todas las bases que Binance tiene con USDT
            for base in sorted(by_base.keys()):
                in_top200 = base in cmc_set
                syms_join = ",".join(sorted(by_base[base]))
                w.writerow([base, True, in_top200, syms_join])
            # Bases en CMC que NO están como USDT en Binance
            binance_bases = set(by_base.keys())
            for base in sorted(cmc_set - binance_bases):
                w.writerow([base, False, True, ""])

        return universe_csv

    # ------------------- Ejecución semanal principal -------------------
    def run_weekly(self, total_budget: float = 0.0):
        cfg_run = self.settings.get("run", {}) or {}
        send_tg = bool(cfg_run.get("send_telegram", False))
        cvd_hours = int(cfg_run.get("cvd_hours", 24))
        ob_levels = int(cfg_run.get("ob_levels", 20))
        req_delay_p1 = float(cfg_run.get("request_delay_seconds_phase1", 0.50))  # Fase 1: klines
        req_delay = float(cfg_run.get("request_delay_seconds", 0.50))            # Fase 2: orderflow
        limit_symbols = int(cfg_run.get("limit_symbols", 0))

        # 1) Universo (Top-200 CMC ∩ Binance USDT)
        top200 = self.cmc.load_top200_cache()                     # lista de 'BASE' (BTC, ETH, ...)
        all_usdt = self.binance.list_usdt_symbols()               # [{"symbol":"BTCUSDT","base":"BTC"}, ...]
        binance_bases = {x["base"] for x in all_usdt}
        cmc_set = {s.upper() for s in top200}
        matched_bases = sorted(list(cmc_set.intersection(binance_bases)))

        print(f"[UNIVERSE] CMC Top200: {len(top200)} | Binance USDT bases: {len(binance_bases)} | Intersección: {len(matched_bases)}")
        universe_csv = self._export_universe_audit(top200, all_usdt)
        print(f"[UNIVERSE] Exported audit to: {universe_csv}")

        if len(matched_bases) == 0:
            print("[UNIVERSE] No CMC Top-200 bases found with USDT pairs on Binance. Check universe CSV and CMC cache.")
            return

        # Símbolos Binance (ej. BTCUSDT, ETHUSDT, ...)
        symbols = self.binance.get_usdt_symbols_intersection(top200)
        if limit_symbols and limit_symbols > 0:
            symbols = symbols[:limit_symbols]

        # === FASE 1: Indicadores + Filtros de Calidad (sin orderflow) ===
        prequalified = []  # [(sym, metrics, qflags)]
        scanned = []       # lista completa para diagnóstico total
        fail_liq = 0
        fail_atr = 0
        exceptions_phase1 = 0
        errors_counter = {}

        for sym in symbols:
            try:
                metrics = compute_indicators_12m(self.binance, sym)
                qflags = pass_quality_filters(self.settings, metrics)

                if not (qflags.liquidity_ok and qflags.atr_ok):
                    reason = []
                    if not qflags.liquidity_ok:
                        reason.append("liquidity")
                        fail_liq += 1
                    if not qflags.atr_ok:
                        reason.append("atr")
                        fail_atr += 1
                    scanned.append(dict(
                        symbol=sym, phase="FILTERED", metrics=metrics, qflags=qflags,
                        order=None, scores=None, zone=None, fail_reason=" & ".join(reason)
                    ))
                else:
                    prequalified.append((sym, metrics, qflags))
                    scanned.append(dict(
                        symbol=sym, phase="EVALUATED", metrics=metrics, qflags=qflags,
                        order=None, scores=None, zone=None, fail_reason=None
                    ))

                time.sleep(req_delay_p1)  # control de tasa Fase 1

            except Exception as e:
                exceptions_phase1 += 1
                # incluye tipo de excepción y símbolo para depurar rápido
                msg = f"exception_phase1: {type(e).__name__}: {str(e)[:160]} (symbol={sym})"
                errors_counter[msg] = errors_counter.get(msg, 0) + 1
                scanned.append(dict(
                    symbol=sym, phase="FILTERED", metrics=None, qflags=None,
                    order=None, scores=None, zone=None, fail_reason=msg
                ))
                time.sleep(req_delay_p1)
                continue

        print(f"[PHASE1] Symbols scanned: {len(symbols)} | Prequalified (passed quality): {len(prequalified)} | Failed liquidity: {fail_liq} | Failed ATR: {fail_atr} | Exceptions: {exceptions_phase1}")
        if errors_counter:
            print("[PHASE1] Top exception reasons:")
            for k, v in sorted(errors_counter.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"  x{v} -> {k}")

        if not prequalified:
            # Export diagnóstico completo hasta aquí y salir con reporte vacío
            diag_full = export_diagnostics_full(self.settings, scanned, out_dir="data/snapshots")
            print(f"[DIAG] Full diagnostics saved to: {diag_full}")
            lane_decisions = {"BTC": "PAUSE", "ETH": "PAUSE"}
            eligible = []
            allocation = allocate_budgets(self.settings, lane_decisions, total_budget, eligible)
            export_weekly(self.persistence, lane_decisions, allocation, [], eligible)
            msg = format_weekly_message(self.settings, lane_decisions, allocation, [], eligible)
            print("\n=== TELEGRAM MESSAGE PREVIEW ===\n" + msg + "\n")
            if send_tg:
                self.tg.send_message(msg)
            return

        # === FASE 2: Orderflow + Scoring + Clasificación (solo prequalified) ===
        rows = []              # (sym, metrics, order, scores, zone)
        exceptions_phase2 = 0

        for sym, metrics, qflags in prequalified:
            try:
                order = compute_orderflow(self.binance, sym, hours=cvd_hours, ob_levels=ob_levels)
                scores = compute_buy_score(self.settings, metrics, order)
                zone = classify_zone(self.settings, metrics, order, scores)

                rows.append((sym, metrics, order, scores, zone))
                # completar/duplicar entrada en 'scanned' con order/score/zone
                scanned.append(dict(
                    symbol=sym, phase="EVALUATED", metrics=metrics, qflags=qflags,
                    order=order, scores=scores, zone=zone, fail_reason=None
                ))

                time.sleep(req_delay)  # control de tasa Fase 2

            except Exception as e:
                exceptions_phase2 += 1
                msg = f"exception_phase2: {type(e).__name__}: {str(e)[:160]} (symbol={sym})"
                scanned.append(dict(
                    symbol=sym, phase="FILTERED", metrics=metrics, qflags=qflags,
                    order=None, scores=None, zone=None, fail_reason=msg
                ))
                time.sleep(req_delay)
                continue

        print(f"[PHASE2] Evaluated (orderflow+score): {len(rows)} | Exceptions: {exceptions_phase2}")

        # 3) Decisiones por carril y elegibles Top-20
        lane_decisions = decide_lanes(self.settings, rows)
        eligible = select_top20_eligible(self.settings, rows)

        # 4) Asignación de presupuesto
        allocation = allocate_budgets(self.settings, lane_decisions, total_budget, eligible)

        # ---------- Entry Triggers (compra) para mostrar en Telegram ----------
        cfg_signals = self.settings.get("signals", {}) or {}
        cfg_entry = self.settings.get("entry_trailing", {}) or {}
        near_sma_mult = float(cfg_signals.get("near_sma_mult", 1.08))
        lookback_days = int(cfg_entry.get("lookback_days_for_min", 10))
        trigger_from_min_pct = float(cfg_entry.get("trigger_from_min_pct", 0.03))

        entry_triggers = {}
        # Nota: 'metrics' debería proveer la serie de cierres ('closes').
        # Si aún no la expones en SymbolMetrics, añade 'closes' en features/indicators.py.
        for sym, m, o, s, z in rows:
            try:
                closes = getattr(m, "closes", None) or getattr(o, "closes", None)
                if not closes:
                    continue
                trig = build_entry_trigger(
                    symbol=sym,
                    closes=closes,
                    sma200=m.sma200,
                    near_sma_mult=near_sma_mult,
                    lookback_days=lookback_days,
                    trigger_from_min_pct=trigger_from_min_pct,
                )
                if trig:
                    entry_triggers[sym] = trig
            except Exception:
                continue

        # 5) Export básico
        export_weekly(self.persistence, lane_decisions, allocation, rows, eligible)

        # 6) Diagnóstico detallado (CSV compacto + CSV completo) + resumen
        diag_path = export_diagnostics(self.persistence, self.settings, rows, eligible, lane_decisions)
        print(f"[DIAG] Wrote detailed diagnostics to: {diag_path}")

        failed_counts = dict(score_ok=0, vol_ok=0, taker_buy_dom_ok=0, ob_bid_ok=0, near_sma200_ok=0)
        total_eval = 0
        for sym, m, o, score, zone in rows:
            _, flags, _ = _reason_and_flags(self.settings, m, o, score)
            total_eval += 1
            for k in failed_counts:
                if not flags[k]:
                    failed_counts[k] += 1

        total_scanned = len(scanned)
        passed_quality = len([r for r in scanned if r["phase"] == "EVALUATED" and r["order"] is None and r["scores"] is None])
        print(f"[SUMMARY] Scanned symbols: {total_scanned} | Passed quality (phase1): {passed_quality} | Exceptions p1: {exceptions_phase1} | Exceptions p2: {exceptions_phase2}")
        print("[SUMMARY] Evaluated (after quality):", total_eval)
        for k, v in failed_counts.items():
            print(f"[SUMMARY] Not passing {k}: {v}")

        diag_full = export_diagnostics_full(self.settings, scanned, out_dir="data/snapshots")
        print(f"[DIAG] Full diagnostics saved to: {diag_full}")

        # 7) Mensaje Telegram (preview y envío opcional)
        #   Paso 'entry_triggers' como kwarg opcional para no romper tu formatter si aún no lo soporta.
        try:
            msg = format_weekly_message(
                self.settings, lane_decisions, allocation, rows, eligible, entry_triggers=entry_triggers
            )
        except TypeError:
            # compat: versión antigua del formatter sin entry_triggers
            msg = format_weekly_message(self.settings, lane_decisions, allocation, rows, eligible)

        print("\n=== TELEGRAM MESSAGE PREVIEW ===\n" + msg + "\n")
        if send_tg:
            self.tg.send_message(msg)
