from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from telemetry_analytics.db import connect, initialize_schema, table_exists
from telemetry_analytics.ingestion.load import load_telemetry_dataset
from telemetry_analytics.normalize.models import NORMALIZED_TABLES
from telemetry_analytics.normalize.telemetry import NormalizedTelemetry


TABLE_COLUMNS = {
    "raw_log_batches": [
        "batch_id",
        "source_file",
        "line_number",
        "message_type",
        "owner",
        "log_group",
        "log_stream",
        "subscription_filters",
        "partition_year",
        "partition_month",
        "partition_day",
        "raw_json",
    ],
    "raw_log_events": [
        "log_event_id",
        "batch_id",
        "event_index",
        "ingestion_timestamp_ms",
        "batch_date",
        "raw_message_json",
        "raw_log_event_json",
        "parse_status",
        "parse_error",
    ],
    "events": [
        "event_id",
        "log_event_id",
        "event_type",
        "event_name",
        "event_timestamp_utc",
        "session_id",
        "organization_id",
        "user_email",
        "user_id",
        "user_account_uuid",
        "terminal_type",
        "scope_name",
        "scope_version",
        "host_arch",
        "host_name",
        "os_type",
        "os_version",
        "service_name",
        "service_version",
        "user_profile",
        "user_serial",
        "attributes_json",
        "resource_json",
    ],
    "api_requests": [
        "event_id",
        "model",
        "cost_usd",
        "duration_ms",
        "input_tokens",
        "output_tokens",
        "cache_read_tokens",
        "cache_creation_tokens",
    ],
    "api_errors": ["event_id", "model", "status_code", "error_text", "duration_ms", "attempt"],
    "tool_decisions": ["event_id", "tool_name", "decision", "source"],
    "tool_results": [
        "event_id",
        "tool_name",
        "decision_type",
        "decision_source",
        "success",
        "duration_ms",
        "tool_result_size_bytes",
    ],
    "user_prompts": ["event_id", "prompt_redacted", "prompt_length"],
    "employees": ["email", "full_name", "practice", "level", "location"],
}


@dataclass(frozen=True)
class IngestionSummary:
    db_path: Path
    row_counts: dict[str, int]
    parse_errors: int
    normalization_errors: int


def refresh_database(
    db_path: str | Path,
    telemetry_path: str | Path,
    employees_path: str | Path,
) -> IngestionSummary:
    normalized = load_telemetry_dataset(telemetry_path, employees_path)
    reset_database_file(db_path)

    with connect(db_path) as conn:
        initialize_schema(conn)
        insert_normalized_telemetry(conn, normalized)
        row_counts = count_tables(conn)

    return IngestionSummary(
        db_path=Path(db_path),
        row_counts=row_counts,
        parse_errors=len(normalized.parse_errors),
        normalization_errors=len(normalized.normalization_errors),
    )


def reset_database_file(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for candidate in (path, Path(f"{path}.wal")):
        if candidate.exists():
            candidate.unlink()


def insert_normalized_telemetry(conn: Any, normalized: NormalizedTelemetry) -> None:
    for table_name in NORMALIZED_TABLES:
        rows = getattr(normalized, table_name)
        insert_rows(conn, table_name, rows)


def insert_rows(conn: Any, table_name: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return

    columns = TABLE_COLUMNS[table_name]
    placeholders = ", ".join(["?"] * len(columns))
    quoted_columns = ", ".join(columns)
    values = [tuple(row.get(column) for column in columns) for row in rows]
    conn.executemany(
        f"INSERT INTO {table_name} ({quoted_columns}) VALUES ({placeholders})",
        values,
    )


def count_tables(conn: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table_name in NORMALIZED_TABLES:
        if table_exists(conn, table_name):
            counts[table_name] = conn.execute(f"SELECT count(*) FROM {table_name}").fetchone()[0]
    return counts
