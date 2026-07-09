from __future__ import annotations

import json
import unittest
from datetime import timezone
from pathlib import Path

from telemetry_analytics.ingestion.employees import (
    enrich_event_rows,
    index_employees_by_email,
    load_employees_csv,
)
from telemetry_analytics.ingestion.load import load_telemetry_dataset, load_telemetry_jsonl


FIXTURE_DIR = Path(__file__).parent / "fixtures"


class IngestionNormalizationTest(unittest.TestCase):
    def test_load_telemetry_jsonl_normalizes_all_known_event_types(self) -> None:
        normalized = load_telemetry_jsonl(FIXTURE_DIR / "telemetry_logs.jsonl")

        self.assertEqual(len(normalized.raw_log_batches), 1)
        self.assertEqual(len(normalized.raw_log_events), 5)
        self.assertEqual(len(normalized.events), 5)
        self.assertEqual(len(normalized.api_requests), 1)
        self.assertEqual(len(normalized.api_errors), 1)
        self.assertEqual(len(normalized.tool_decisions), 1)
        self.assertEqual(len(normalized.tool_results), 1)
        self.assertEqual(len(normalized.user_prompts), 1)
        self.assertEqual(normalized.parse_errors, [])
        self.assertEqual(normalized.normalization_errors, [])

        event = normalized.events[0]
        self.assertEqual(event["event_type"], "claude_code.api_request")
        self.assertEqual(event["event_name"], "api_request")
        self.assertEqual(event["event_timestamp_utc"].tzinfo, timezone.utc)
        self.assertEqual(event["session_id"], "session-1")
        self.assertEqual(event["user_email"], "alex.chen@example.com")
        self.assertEqual(event["scope_version"], "2.1.39")
        self.assertEqual(event["host_arch"], "arm64")
        self.assertEqual(json.loads(event["attributes_json"])["event.name"], "api_request")

        api_request = normalized.api_requests[0]
        self.assertEqual(api_request["model"], "claude-opus-4-6")
        self.assertEqual(api_request["cost_usd"], 0.125)
        self.assertEqual(api_request["duration_ms"], 1234)
        self.assertEqual(api_request["input_tokens"], 100)
        self.assertEqual(api_request["output_tokens"], 25)
        self.assertEqual(api_request["cache_read_tokens"], 1000)
        self.assertEqual(api_request["cache_creation_tokens"], 50)

        api_error = normalized.api_errors[0]
        self.assertEqual(api_error["status_code"], "429")
        self.assertEqual(api_error["attempt"], 2)
        self.assertEqual(api_error["duration_ms"], 500)

        tool_result = normalized.tool_results[0]
        self.assertIs(tool_result["success"], True)
        self.assertEqual(tool_result["duration_ms"], 34)
        self.assertEqual(tool_result["tool_result_size_bytes"], 2048)

        user_prompt = normalized.user_prompts[0]
        self.assertIs(user_prompt["prompt_redacted"], True)
        self.assertEqual(user_prompt["prompt_length"], 256)

        raw_log_event = normalized.raw_log_events[0]
        self.assertEqual(raw_log_event["parse_status"], "parsed")
        self.assertIsNotNone(json.loads(raw_log_event["raw_message_json"])["body"])

    def test_employee_csv_loading_and_email_enrichment(self) -> None:
        employees = load_employees_csv(FIXTURE_DIR / "employees.csv")
        employees_by_email = index_employees_by_email(employees)
        normalized = load_telemetry_jsonl(FIXTURE_DIR / "telemetry_logs.jsonl")
        enriched = enrich_event_rows(normalized.events, employees)

        self.assertEqual(employees_by_email["alex.chen@example.com"]["practice"], "Data Engineering")
        self.assertEqual(enriched[0]["employee_full_name"], "Alex Chen")
        self.assertEqual(enriched[0]["employee_location"], "United States")

    def test_load_telemetry_dataset_includes_employee_rows(self) -> None:
        normalized = load_telemetry_dataset(
            FIXTURE_DIR / "telemetry_logs.jsonl",
            FIXTURE_DIR / "employees.csv",
        )

        self.assertEqual(len(normalized.events), 5)
        self.assertEqual(len(normalized.employees), 1)
        self.assertEqual(normalized.employees[0]["email"], "alex.chen@example.com")

    def test_malformed_batches_and_nested_messages_are_reported(self) -> None:
        normalized = load_telemetry_jsonl(FIXTURE_DIR / "malformed_telemetry_logs.jsonl")

        self.assertEqual(len(normalized.parse_errors), 2)
        self.assertEqual(len(normalized.raw_log_batches), 1)
        self.assertEqual(len(normalized.raw_log_events), 1)
        self.assertEqual(normalized.raw_log_events[0]["parse_status"], "parse_error")
        self.assertIn("invalid nested message", normalized.raw_log_events[0]["parse_error"])
        self.assertEqual(normalized.events, [])


if __name__ == "__main__":
    unittest.main()
