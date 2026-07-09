from __future__ import annotations

import json
import unittest

from telemetry_analytics.ingestion.parser import iter_log_events, parse_batch_line


class ParserContractTest(unittest.TestCase):
    def test_parse_batch_line_and_nested_message(self) -> None:
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
            "logEvents": [
                {"id": "event-1", "timestamp": 1767261600000, "message": json.dumps(message)}
            ],
            "year": 2026,
            "month": 1,
            "day": 1,
        }

        parsed = parse_batch_line(json.dumps(batch), 1)
        events = list(iter_log_events(parsed))

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].message["body"], "claude_code.api_request")
        self.assertEqual(events[0].message["attributes"]["event.name"], "api_request")

    def test_parse_batch_line_rejects_missing_log_events(self) -> None:
        with self.assertRaisesRegex(ValueError, "missing logEvents"):
            parse_batch_line(json.dumps({"messageType": "DATA_MESSAGE"}), 1)


if __name__ == "__main__":
    unittest.main()
