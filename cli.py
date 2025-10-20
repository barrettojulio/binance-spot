# cli.py
import argparse
import sys
from core.scheduler import run_refresh_cmc, run_weekly


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="institutional_radar",
        description="Binance Spot institutional accumulation radar (weekly runner)"
    )
    p.add_argument(
        "--settings",
        required=True,
        help="Path to settings.yaml (e.g., config/settings.yaml)"
    )

    # Acciones (una a la vez)
    p.add_argument(
        "--refresh-cmc",
        action="store_true",
        help="Refresh CoinMarketCap Top-200 cache (manual)"
    )
    p.add_argument(
        "--run-weekly",
        action="store_true",
        help="Run the weekly analysis and produce Telegram message"
    )

    # Presupuesto (opcional; si no lo pasas, se usa run.default_budget del YAML)
    p.add_argument(
        "--budget",
        type=float,
        default=None,
        help="Weekly total budget in USDT (e.g., 5000). If omitted, uses run.default_budget from settings."
    )
    return p


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    # Validación de acción
    if not (args.refresh_cmc or args.run_weekly):
        print("Nothing to do. Use --refresh-cmc or --run-weekly.")
        return 0

    # Ejecutar acción
    if args.refresh_cmc:
        run_refresh_cmc(args.settings)
        return 0

    if args.run_weekly:
        # budget puede venir None → scheduler tomará fallback de settings.run.default_budget
        run_weekly(args.settings, total_budget=args.budget)
        return 0

    # (no debería llegar aquí)
    print("Nothing to do. Use --refresh-cmc or --run-weekly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
