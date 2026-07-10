from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from telemetry_analytics.db import connect, table_exists
from telemetry_analytics.normalize.models import NORMALIZED_TABLES
from telemetry_analytics.storage.duckdb_store import refresh_database


FIXTURE_DIR = Path(__file__).parent / "fixtures"


class DuckDBStorageTest(unittest.TestCase):
    def test_refresh_database_creates_all_normalized_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "telemetry.duckdb"
            summary = refresh_database(
                db_path,
                FIXTURE_DIR / "telemetry_logs.jsonl",
                FIXTURE_DIR / "employees.csv",
            )

            self.assertTrue(db_path.exists())
            self.assertEqual(summary.parse_errors, 0)
            self.assertEqual(summary.normalization_errors, 0)
            self.assertEqual(summary.row_counts["raw_log_batches"], 1)
            self.assertEqual(summary.row_counts["raw_log_events"], 5)
            self.assertEqual(summary.row_counts["events"], 5)
            self.assertEqual(summary.row_counts["api_requests"], 1)
            self.assertEqual(summary.row_counts["api_errors"], 1)
            self.assertEqual(summary.row_counts["tool_decisions"], 1)
            self.assertEqual(summary.row_counts["tool_results"], 1)
            self.assertEqual(summary.row_counts["user_prompts"], 1)
            self.assertEqual(summary.row_counts["employees"], 1)

            with connect(db_path, read_only=True) as conn:
                for table_name in NORMALIZED_TABLES:
                    self.assertTrue(table_exists(conn, table_name), table_name)

                row = conn.execute(
                    """
                    SELECT e.event_id, e.log_event_id, r.raw_message_json
                    FROM events e
                    JOIN raw_log_events r ON e.log_event_id = r.log_event_id
                    WHERE e.event_id = 'api-request-1'
                    """
                ).fetchone()

            self.assertEqual(row[0], "api-request-1")
            self.assertEqual(row[0], row[1])
            self.assertIn("claude_code.api_request", row[2])

    def test_refresh_database_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "telemetry.duckdb"
            first = refresh_database(
                db_path,
                FIXTURE_DIR / "telemetry_logs.jsonl",
                FIXTURE_DIR / "employees.csv",
            )
            second = refresh_database(
                db_path,
                FIXTURE_DIR / "telemetry_logs.jsonl",
                FIXTURE_DIR / "employees.csv",
            )

            self.assertEqual(first.row_counts, second.row_counts)


if __name__ == "__main__":
    unittest.main()
