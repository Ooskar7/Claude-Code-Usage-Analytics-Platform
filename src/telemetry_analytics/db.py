from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

from telemetry_analytics.config import PROJECT_ROOT, get_settings

SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"


def database_exists(db_path: str | Path | None = None) -> bool:
    path = Path(db_path or get_settings().db_path)
    return path.exists()


def connect(db_path: str | Path | None = None, *, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    path = Path(db_path or get_settings().db_path)
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


def initialize_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute(SCHEMA_PATH.read_text(encoding="utf-8"))


def fetch_one(conn: duckdb.DuckDBPyConnection, sql: str, params: list[Any] | None = None) -> tuple[Any, ...]:
    return conn.execute(sql, params or []).fetchone()
