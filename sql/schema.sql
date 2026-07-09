CREATE TABLE IF NOT EXISTS raw_log_batches (
    batch_id VARCHAR PRIMARY KEY,
    source_file VARCHAR NOT NULL,
    line_number INTEGER NOT NULL,
    message_type VARCHAR,
    owner VARCHAR,
    log_group VARCHAR,
    log_stream VARCHAR,
    subscription_filters JSON,
    partition_year INTEGER,
    partition_month INTEGER,
    partition_day INTEGER,
    raw_json JSON NOT NULL,
    loaded_at_utc TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS raw_log_events (
    log_event_id VARCHAR PRIMARY KEY,
    batch_id VARCHAR NOT NULL,
    event_index INTEGER NOT NULL,
    ingestion_timestamp_ms BIGINT,
    batch_date DATE,
    raw_message_json JSON,
    raw_log_event_json JSON NOT NULL,
    parse_status VARCHAR NOT NULL,
    parse_error VARCHAR,
    loaded_at_utc TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS events (
    event_id VARCHAR PRIMARY KEY,
    log_event_id VARCHAR NOT NULL,
    event_type VARCHAR NOT NULL,
    event_name VARCHAR,
    event_timestamp_utc TIMESTAMP,
    session_id VARCHAR,
    organization_id VARCHAR,
    user_email VARCHAR,
    user_id VARCHAR,
    user_account_uuid VARCHAR,
    terminal_type VARCHAR,
    scope_name VARCHAR,
    scope_version VARCHAR,
    host_arch VARCHAR,
    host_name VARCHAR,
    os_type VARCHAR,
    os_version VARCHAR,
    service_name VARCHAR,
    service_version VARCHAR,
    user_profile VARCHAR,
    user_serial VARCHAR,
    attributes_json JSON NOT NULL,
    resource_json JSON NOT NULL,
    loaded_at_utc TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS api_requests (
    event_id VARCHAR PRIMARY KEY,
    model VARCHAR,
    cost_usd DOUBLE,
    duration_ms BIGINT,
    input_tokens BIGINT,
    output_tokens BIGINT,
    cache_read_tokens BIGINT,
    cache_creation_tokens BIGINT
);

CREATE TABLE IF NOT EXISTS api_errors (
    event_id VARCHAR PRIMARY KEY,
    model VARCHAR,
    status_code VARCHAR,
    error_text VARCHAR,
    duration_ms BIGINT,
    attempt INTEGER
);

CREATE TABLE IF NOT EXISTS tool_decisions (
    event_id VARCHAR PRIMARY KEY,
    tool_name VARCHAR,
    decision VARCHAR,
    source VARCHAR
);

CREATE TABLE IF NOT EXISTS tool_results (
    event_id VARCHAR PRIMARY KEY,
    tool_name VARCHAR,
    decision_type VARCHAR,
    decision_source VARCHAR,
    success BOOLEAN,
    duration_ms BIGINT,
    tool_result_size_bytes BIGINT
);

CREATE TABLE IF NOT EXISTS user_prompts (
    event_id VARCHAR PRIMARY KEY,
    prompt_redacted BOOLEAN,
    prompt_length BIGINT
);

CREATE TABLE IF NOT EXISTS employees (
    email VARCHAR PRIMARY KEY,
    full_name VARCHAR,
    practice VARCHAR,
    level VARCHAR,
    location VARCHAR
);
