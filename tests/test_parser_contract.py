from __future__ import annotations

import json

import pytest

from telemetry_analytics.ingestion.parser import iter_log_events, parse_batch_line


def test_parse_batch_line_and_nested_message() -> None:
    message = {
        "body": "claude_code.api_request",
        "attributes": {
            "event.name": "api_request",
            "event.timestamp": "2026-01-01T10:00:00.000Z",
        },
        "scope": {"name": "com.anthropic.claude_code.events", "version": "2.1.39"},
        "resource": {"service.name": "claude-code-None"},
    }
    batch = {
        "messageType": "DATA_MESSAGE",
        "logEvents": [{"id": "event-1", "timestamp": 1767261600000, "message": json.dumps(message)}],
        "year": 2026,
        "month": 1,
        "day": 1,
    }

    parsed = parse_batch_line(json.dumps(batch), 1)
    events = list(iter_log_events(parsed))

    assert len(events) == 1
    assert events[0].message["body"] == "claude_code.api_request"
    assert events[0].message["attributes"]["event.name"] == "api_request"


def test_parse_batch_line_rejects_missing_log_events() -> None:
    with pytest.raises(ValueError, match="missing logEvents"):
        parse_batch_line(json.dumps({"messageType": "DATA_MESSAGE"}), 1)
