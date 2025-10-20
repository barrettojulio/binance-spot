import argparse
from core.scheduler import run_refresh_cmc, run_weekly

def parse_args():
    p = argparse.ArgumentParser(description="Institutional Spot Radar — Weekly Runner")
    p.add_argument("--settings", type=str, default="config/settings.yaml")
    p.add_argument("--refresh-cmc", action="store_true")
    p.add_argument("--run-weekly", action="store_true")
    p.add_argument("--budget", type=float, default=0.0)
    return p.parse_args()

def main():
    args = parse_args()
    if args.refresh_cmc:
        run_refresh_cmc(args.settings)
    if args.run_weekly:
        run_weekly(args.settings, total_budget=args.budget)
    if not args.refresh_cmc and not args.run_weekly:
        print("Nothing to do. Use --refresh-cmc or --run-weekly.")

if __name__ == "__main__":
    main()
