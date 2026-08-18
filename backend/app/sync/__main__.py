"""CLI entry points:

    python -m app.sync universe [--from-idx]
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

    p_universe = sub.add_parser(
        "universe", help="seed the ticker universe from the bundled snapshot"
    )
    p_universe.add_argument(
        "--from-idx",
        action="store_true",
        help=(
            "fetch from IDX instead of the snapshot. For regenerating "
            "data/idx_universe.csv by hand, from a machine IDX answers; "
            "nothing scheduled does this. See app/sync/universe.py."
        ),
    )

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

    p_stmt = sub.add_parser("statements", help="refresh financial statements")
    p_stmt.add_argument(
        "--tickers", help="comma-separated subset; default = all tracked tickers"
    )

    p_quotes = sub.add_parser("quotes", help="refresh latest_quotes")
    p_quotes.add_argument(
        "--tickers",
        help="comma-separated override; default = held tickers + ^JKSE",
    )

    args = parser.parse_args()

    if args.command == "universe":
        result = asyncio.run(sync_universe(from_idx=args.from_idx))
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
    elif args.command == "statements":
        from app.sync.statements import sync_statements

        subset = args.tickers.split(",") if args.tickers else None
        result = asyncio.run(sync_statements(subset))
        print(
            f"statements: {result.synced} synced ({result.periods} periods), "
            f"{len(result.failed)} failed {result.failed or ''}"
        )
    elif args.command == "quotes":
        override = args.tickers.split(",") if args.tickers else None
        result = asyncio.run(sync_quotes(override))
        print(f"quote refresh: {result.synced} updated, {len(result.failed)} failed {result.failed or ''}")


if __name__ == "__main__":
    main()
