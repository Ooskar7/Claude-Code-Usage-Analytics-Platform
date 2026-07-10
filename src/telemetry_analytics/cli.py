from __future__ import annotations

import argparse

from telemetry_analytics.config import get_settings
from telemetry_analytics.db import connect, initialize_schema
from telemetry_analytics.storage.duckdb_store import refresh_database


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Claude Code telemetry analytics utilities")
    subcommands = parser.add_subparsers(dest="command", required=True)

    init_db = subcommands.add_parser("init-db", help="Create the DuckDB normalized schema")
    init_db.add_argument("--db-path", default=None, help="DuckDB database path")

    ingest = subcommands.add_parser("ingest", help="Refresh DuckDB from generated telemetry files")
    ingest.add_argument("--telemetry-path", default=None, help="Path to telemetry_logs.jsonl")
    ingest.add_argument("--employees-path", default=None, help="Path to employees.csv")
    ingest.add_argument("--db-path", default=None, help="DuckDB database path")

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

    if args.command == "ingest":
        db_path = args.db_path or settings.db_path
        telemetry_path = args.telemetry_path or settings.raw_dir / "telemetry_logs.jsonl"
        employees_path = args.employees_path or settings.raw_dir / "employees.csv"
        summary = refresh_database(db_path, telemetry_path, employees_path)
        print(f"Refreshed DuckDB database at {summary.db_path}")
        for table_name, row_count in summary.row_counts.items():
            print(f"  {table_name}: {row_count}")
        print(f"  parse_errors: {summary.parse_errors}")
        print(f"  validation_errors: {summary.validation_errors}")
        print(f"  normalization_errors: {summary.normalization_errors}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
