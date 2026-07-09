COMMON_EVENT_COLUMNS = [
    "event_id",
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
]

NORMALIZED_TABLES = [
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

EVENT_BODY_TABLES = {
    "claude_code.api_request": "api_requests",
    "claude_code.api_error": "api_errors",
    "claude_code.tool_decision": "tool_decisions",
    "claude_code.tool_result": "tool_results",
    "claude_code.user_prompt": "user_prompts",
}
