from __future__ import annotations

import argparse

from telemetry_analytics.config import get_settings
from telemetry_analytics.db import connect, initialize_schema


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claude Code telemetry analytics utilities")
    subcommands = parser.add_subparsers(dest="command", required=True)

    init_db = subcommands.add_parser("init-db", help="Create the DuckDB normalized schema")
    init_db.add_argument("--db-path", default=None, help="DuckDB database path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = get_settings()

    if args.command == "init-db":
        db_path = args.db_path or settings.db_path
        with connect(db_path) as conn:
            initialize_schema(conn)
        print(f"Initialized DuckDB schema at {db_path}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
