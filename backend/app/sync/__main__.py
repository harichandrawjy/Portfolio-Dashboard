"""CLI entry point: python -m app.sync universe"""

import argparse
import asyncio
import logging

from app.sync.universe import sync_universe


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(prog="python -m app.sync")
    parser.add_argument("command", choices=["universe"])
    args = parser.parse_args()

    if args.command == "universe":
        result = asyncio.run(sync_universe())
        print(
            f"universe sync [{result.source}]: "
            f"+{result.inserted} inserted, {result.updated} updated, "
            f"{result.deactivated} deactivated, {result.total_active} active stocks"
        )


if __name__ == "__main__":
    main()
