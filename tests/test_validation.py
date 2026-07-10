from __future__ import annotations

import json
from pathlib import Path

from telemetry_analytics.ingestion.load import load_telemetry_dataset, load_telemetry_jsonl
from telemetry_analytics.storage.duckdb_store import refresh_database


def common_message(**attribute_overrides: str) -> dict:
    attributes = {
        "event.timestamp": "2026-01-01T10:00:00.000Z",
        "event.name": "api_request",
        "organization.id": "org-1",
        "session.id": "session-1",
        "terminal.type": "vscode",
        "user.account_uuid": "account-1",
        "user.email": "alex.chen@example.com",
        "user.id": "user-1",
        "model": "claude-opus-4-6",
        "cost_usd": "0.125",
        "duration_ms": "1234",
        "input_tokens": "100",
        "output_tokens": "25",
        "cache_read_tokens": "1000",
        "cache_creation_tokens": "50",
    }
    attributes.update(attribute_overrides)
    return {
        "body": "claude_code.api_request",
        "attributes": attributes,
        "scope": {"name": "com.anthropic.claude_code.events", "version": "2.1.39"},
        "resource": {
            "host.arch": "arm64",
            "host.name": "dev-host",
            "os.type": "darwin",
            "os.version": "24.6.0",
            "service.name": "claude-code-None",
            "service.version": "2.1.39",
            "user.email": "",
            "user.practice": "Data Engineering",
            "user.profile": "alex",
            "user.serial": "SERIAL1",
        },
    }


def batch_for_messages(messages: list[dict | str]) -> str:
    log_events = []
    for index, message in enumerate(messages):
        raw_message = message if isinstance(message, str) else json.dumps(message)
        log_events.append(
            {
                "id": f"event-{index}",
                "timestamp": 1767261600000 + index,
                "message": raw_message,
            }
        )
    return json.dumps(
        {
            "messageType": "DATA_MESSAGE",
            "owner": "123456789012",
            "logGroup": "/claude-code/telemetry",
            "logStream": "otel-collector",
            "subscriptionFilters": ["logs-to-s3"],
            "year": 2026,
            "month": 1,
            "day": 1,
            "logEvents": log_events,
        }
    )


def write_employees(path: Path, *, email: str = "alex.chen@example.com") -> None:
    path.write_text(
        "email,full_name,practice,level,location\n"
        f"{email},Alex Chen,Data Engineering,L5,United States\n",
        encoding="utf-8",
    )


def test_missing_telemetry_input_file_is_reported(tmp_path: Path) -> None:
    missing = tmp_path / "missing.jsonl"

    normalized = load_telemetry_jsonl(missing)

    assert normalized.events == []
    assert len(normalized.validation_errors) == 1
    assert "missing input file" in normalized.validation_errors[0].message


def test_missing_employee_input_file_is_reported_without_crashing(tmp_path: Path) -> None:
    telemetry = tmp_path / "telemetry_logs.jsonl"
    telemetry.write_text(batch_for_messages([common_message()]) + "\n", encoding="utf-8")

    normalized = load_telemetry_dataset(telemetry, tmp_path / "missing_employees.csv")

    assert len(normalized.events) == 1
    assert len(normalized.validation_errors) == 1
    assert "missing input file" in normalized.validation_errors[0].message


def test_malformed_jsonl_and_invalid_logevents_are_parse_errors(tmp_path: Path) -> None:
    telemetry = tmp_path / "telemetry_logs.jsonl"
    telemetry.write_text(
        "{not json}\n"
        + json.dumps({"messageType": "DATA_MESSAGE"}) + "\n"
        + json.dumps({"messageType": "DATA_MESSAGE", "logEvents": "not-a-list"}) + "\n",
        encoding="utf-8",
    )

    normalized = load_telemetry_jsonl(telemetry)

    assert len(normalized.parse_errors) == 3
    assert any("invalid JSONL batch" in error.message for error in normalized.parse_errors)
    assert any("missing logEvents" in error.message for error in normalized.parse_errors)
    assert any("logEvents must be a list" in error.message for error in normalized.parse_errors)


def test_invalid_nested_message_json_is_quarantined(tmp_path: Path) -> None:
    telemetry = tmp_path / "telemetry_logs.jsonl"
    telemetry.write_text(batch_for_messages(["{not nested json"]) + "\n", encoding="utf-8")

    normalized = load_telemetry_jsonl(telemetry)

    assert len(normalized.parse_errors) == 1
    assert len(normalized.raw_log_events) == 1
    assert normalized.raw_log_events[0]["parse_status"] == "parse_error"
    assert "invalid nested message" in normalized.raw_log_events[0]["parse_error"]


def test_missing_required_common_fields_are_validation_errors(tmp_path: Path) -> None:
    telemetry = tmp_path / "telemetry_logs.jsonl"
    message = common_message()
    del message["attributes"]["session.id"]
    telemetry.write_text(batch_for_messages([message]) + "\n", encoding="utf-8")

    normalized = load_telemetry_jsonl(telemetry)

    assert normalized.events == []
    assert len(normalized.validation_errors) == 1
    assert "missing required common field" in normalized.validation_errors[0].message
    assert normalized.raw_log_events[0]["parse_status"] == "validation_error"


def test_numeric_and_timestamp_coercion_failures_are_normalization_errors(tmp_path: Path) -> None:
    telemetry = tmp_path / "telemetry_logs.jsonl"
    bad_number = common_message(input_tokens="not-an-int")
    bad_timestamp = common_message(**{"event.timestamp": "not-a-timestamp"})
    telemetry.write_text(batch_for_messages([bad_number, bad_timestamp]) + "\n", encoding="utf-8")

    normalized = load_telemetry_jsonl(telemetry)

    assert normalized.events == []
    assert len(normalized.normalization_errors) == 2
    assert {row["parse_status"] for row in normalized.raw_log_events} == {"normalization_error"}


def test_employee_enrichment_mismatch_is_reported(tmp_path: Path) -> None:
    telemetry = tmp_path / "telemetry_logs.jsonl"
    employees = tmp_path / "employees.csv"
    telemetry.write_text(batch_for_messages([common_message()]) + "\n", encoding="utf-8")
    write_employees(employees, email="different@example.com")

    normalized = load_telemetry_dataset(telemetry, employees)

    assert len(normalized.events) == 1
    assert len(normalized.validation_errors) == 1
    assert "employee enrichment mismatch" in normalized.validation_errors[0].message


def test_database_ingestion_reports_validation_and_normalization_errors(tmp_path: Path) -> None:
    telemetry = tmp_path / "telemetry_logs.jsonl"
    employees = tmp_path / "employees.csv"
    message = common_message(input_tokens="not-an-int")
    telemetry.write_text(batch_for_messages([message]) + "\n", encoding="utf-8")
    write_employees(employees)

    summary = refresh_database(tmp_path / "telemetry.duckdb", telemetry, employees)

    assert summary.row_counts["events"] == 0
    assert summary.normalization_errors == 1
    assert summary.validation_errors == 0
