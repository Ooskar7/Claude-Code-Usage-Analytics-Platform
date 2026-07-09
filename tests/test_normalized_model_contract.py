from telemetry_analytics.normalize.models import COMMON_EVENT_COLUMNS, NORMALIZED_TABLES


def test_normalized_tables_match_agent_contract() -> None:
    assert NORMALIZED_TABLES == [
        "raw_log_batches",
        "raw_log_events",
        "events",
        "api_requests",
        "api_errors",
        "tool_decisions",
        "tool_results",
        "user_prompts",
        "employees",
    ]


def test_common_event_columns_include_traceability_and_environment() -> None:
    required = {
        "event_id",
        "event_type",
        "event_timestamp_utc",
        "session_id",
        "user_email",
        "scope_version",
        "host_arch",
        "os_type",
        "service_version",
        "attributes_json",
        "resource_json",
    }
    assert required.issubset(COMMON_EVENT_COLUMNS)
