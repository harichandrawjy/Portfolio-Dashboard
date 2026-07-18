"""CLI entry points:

    python -m app.sync universe
    python -m app.sync backfill --ticker BBCA [--ticker TLKM ...] [--years 5]
    python -m app.sync daily
    python -m app.sync quotes [--tickers BBCA,TLKM]
"""

import argparse
import asyncio
import logging

from app.sync.prices import backfill_many, sync_daily, sync_quotes
from app.sync.universe import sync_universe


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(prog="python -m app.sync")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("universe", help="refresh the IDX ticker universe")

    p_backfill = sub.add_parser("backfill", help="backfill daily OHLCV history")
    p_backfill.add_argument(
        "--ticker", action="append", required=True, dest="tickers",
        help="IDX code (BBCA) or Yahoo symbol (^JKSE); repeatable",
    )
    p_backfill.add_argument("--years", type=int, default=5)

    sub.add_parser("daily", help="append recent bars for all tracked tickers")

    sub.add_parser("stats", help="rebuild the security_stats cache")

    p_fund = sub.add_parser("fundamentals", help="refresh Yahoo fundamentals")
    p_fund.add_argument(
        "--tickers", help="comma-separated subset; default = all tracked tickers"
    )

    p_quotes = sub.add_parser("quotes", help="refresh latest_quotes")
    p_quotes.add_argument(
        "--tickers",
        help="comma-separated override; default = held tickers + ^JKSE",
    )

    args = parser.parse_args()

    if args.command == "universe":
        result = asyncio.run(sync_universe())
        print(
            f"universe sync [{result.source}]: "
            f"+{result.inserted} inserted, {result.updated} updated, "
            f"{result.deactivated} deactivated, {result.total_active} active stocks"
        )
    elif args.command == "backfill":
        results = asyncio.run(backfill_many(args.tickers, years=args.years))
        for r in results:
            status = f"{r.rows} bars" if r.resolved else "FAILED (not activated)"
            print(f"backfill {r.ticker} ({r.symbol}): {status}")
    elif args.command == "daily":
        result = asyncio.run(sync_daily())
        print(f"daily sync: {result.synced} synced, {len(result.failed)} failed {result.failed or ''}")
    elif args.command == "stats":
        from app.sync.stats import refresh_stats

        count = asyncio.run(refresh_stats())
        print(f"stats refreshed for {count} ticker(s)")
    elif args.command == "fundamentals":
        from app.sync.fundamentals import sync_fundamentals

        subset = args.tickers.split(",") if args.tickers else None
        result = asyncio.run(sync_fundamentals(subset))
        print(
            f"fundamentals: {result.synced} synced, "
            f"{len(result.failed)} failed {result.failed or ''}"
        )
    elif args.command == "quotes":
        override = args.tickers.split(",") if args.tickers else None
        result = asyncio.run(sync_quotes(override))
        print(f"quote refresh: {result.synced} updated, {len(result.failed)} failed {result.failed or ''}")


if __name__ == "__main__":
    main()
