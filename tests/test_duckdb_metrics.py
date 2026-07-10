from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from telemetry_analytics.db import connect
from telemetry_analytics.metrics.duckdb_metrics import (
    active_users_and_sessions,
    api_error_metrics,
    cost_token_totals,
    daily_usage_trends,
    environment_breakdown,
    model_usage,
    overview_kpis,
    prompt_metrics,
    tool_usage,
    usage_by_level,
    usage_by_location,
    usage_by_practice,
)
from telemetry_analytics.storage.duckdb_store import refresh_database


FIXTURE_DIR = Path(__file__).parent / "fixtures"


class DuckDBMetricsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "telemetry.duckdb"
        refresh_database(
            self.db_path,
            FIXTURE_DIR / "telemetry_logs.jsonl",
            FIXTURE_DIR / "employees.csv",
        )
        self.conn = connect(self.db_path, read_only=True)

    def tearDown(self) -> None:
        self.conn.close()
        self.tmpdir.cleanup()

    def test_overview_kpis_use_precise_denominators(self) -> None:
        metrics = overview_kpis(self.conn)

        self.assertEqual(metrics["active_users"], 1)
        self.assertEqual(metrics["sessions"], 1)
        self.assertEqual(metrics["total_events"], 5)
        self.assertEqual(metrics["prompts"], 1)
        self.assertEqual(metrics["api_requests"], 1)
        self.assertEqual(metrics["api_errors"], 1)
        self.assertEqual(metrics["total_tokens"], 1175)
        self.assertAlmostEqual(metrics["total_cost_usd"], 0.125)
        self.assertAlmostEqual(metrics["api_error_rate_api_errors_per_api_request"], 1.0)
        self.assertAlmostEqual(metrics["accepted_tool_decisions_per_tool_decision"], 1.0)
        self.assertAlmostEqual(metrics["successful_tool_results_per_tool_result"], 1.0)

    def test_daily_usage_active_sessions_prompt_cost_and_token_metrics(self) -> None:
        daily = daily_usage_trends(self.conn)
        active = active_users_and_sessions(self.conn)
        prompts = prompt_metrics(self.conn)
        cost = cost_token_totals(self.conn)

        self.assertEqual(len(daily), 1)
        self.assertEqual(daily[0]["active_users"], 1)
        self.assertEqual(daily[0]["sessions"], 1)
        self.assertEqual(daily[0]["prompts"], 1)
        self.assertEqual(daily[0]["api_requests"], 1)
        self.assertEqual(daily[0]["api_errors"], 1)
        self.assertEqual(daily[0]["total_tokens"], 1175)
        self.assertAlmostEqual(daily[0]["total_cost_usd"], 0.125)

        self.assertEqual(active["active_users"], 1)
        self.assertEqual(active["sessions"], 1)
        self.assertEqual(active["avg_session_duration_ms"], 4000)

        self.assertEqual(prompts["prompts"], 1)
        self.assertEqual(prompts["min_prompt_length"], 256)
        self.assertEqual(prompts["max_prompt_length"], 256)

        self.assertEqual(cost["api_requests"], 1)
        self.assertEqual(cost["input_tokens"], 100)
        self.assertEqual(cost["output_tokens"], 25)
        self.assertEqual(cost["cache_read_tokens"], 1000)
        self.assertEqual(cost["cache_creation_tokens"], 50)
        self.assertEqual(cost["total_tokens"], 1175)

    def test_model_tool_error_cohort_and_environment_breakdowns(self) -> None:
        model = model_usage(self.conn)[0]
        practice = usage_by_practice(self.conn)[0]
        level = usage_by_level(self.conn)[0]
        location = usage_by_location(self.conn)[0]
        tool = tool_usage(self.conn)[0]
        errors = api_error_metrics(self.conn)
        environment = environment_breakdown(self.conn)

        self.assertEqual(model["model"], "claude-opus-4-6")
        self.assertEqual(model["api_requests"], 1)
        self.assertEqual(model["api_errors"], 1)
        self.assertAlmostEqual(model["api_error_rate_api_errors_per_api_request"], 1.0)
        self.assertEqual(model["avg_request_duration_ms"], 1234)
        self.assertEqual(model["total_tokens"], 1175)

        self.assertEqual(practice["practice"], "Data Engineering")
        self.assertEqual(practice["active_users"], 1)
        self.assertEqual(level["level"], "L5")
        self.assertEqual(location["location"], "United States")

        self.assertEqual(tool["tool_name"], "Read")
        self.assertEqual(tool["tool_decisions"], 1)
        self.assertEqual(tool["accepted_tool_decisions"], 1)
        self.assertEqual(tool["tool_results"], 1)
        self.assertEqual(tool["successful_tool_results"], 1)
        self.assertEqual(tool["avg_tool_duration_ms"], 34)

        self.assertEqual(errors["summary"]["api_errors"], 1)
        self.assertEqual(errors["summary"]["api_requests"], 1)
        self.assertEqual(errors["status_code_mix"][0]["status_code"], "429")
        self.assertEqual(errors["model_breakdown"][0]["model"], "claude-opus-4-6")

        self.assertEqual(environment["terminal_type"][0]["terminal_type"], "vscode")
        self.assertEqual(environment["os_type"][0]["os_type"], "darwin")
        self.assertEqual(environment["service_version"][0]["service_version"], "2.1.39")


if __name__ == "__main__":
    unittest.main()
