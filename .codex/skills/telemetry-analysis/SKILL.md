---
name: telemetry-analysis
description: Analyze Claude Code telemetry datasets for the internship analytics platform. Use when Codex needs to ingest nested telemetry_logs.jsonl batches, parse logEvents message JSON strings, normalize Claude Code events, join employees.csv enrichment, compute usage/cost/token/tool/error metrics, design dashboards, write data tests, or document the telemetry analytics solution.
---

# Telemetry Analysis

## Overview

Use this skill to build and maintain the Claude Code usage analytics assignment. Treat the agent setup itself as a deliverable: keep parsing assumptions, data contracts, metrics, tests, and commands reproducible in the repository.

## Assignment Goal

Build an end-to-end analytics platform that processes Claude Code telemetry data and presents actionable interactive dashboards. The final solution must include data ingestion, storage or retrieval, cleaning, analytics, visualization, a single documented startup command, tests, documentation, and the committed tuned agent setup.

## Dataset Files

Primary source directory: `claude_code_telemetry/`.

- `generate_fake_data.py`: creates synthetic telemetry using only the Python standard library.
- `README.md`: describes generator options and output files.
- `telemetry_logs.jsonl`: generated JSONL file; each line is a batch, not a single telemetry event.
- `employees.csv`: generated employee table keyed by `email`.

Employee schema:

```text
email,full_name,practice,level,location
```

## Nested JSONL Contract

Always parse telemetry in two JSON stages:

```text
JSONL line
  batch
    messageType
    owner
    logGroup
    logStream
    subscriptionFilters
    year, month, day
    logEvents[]
      id
      timestamp
      message: JSON string
        body
        attributes
        scope
        resource
```

Rules:

- Parse the JSONL line into a batch object.
- Iterate `batch["logEvents"]`.
- Parse `log_event["message"]` as JSON to get the telemetry event.
- Use `event["body"]` as the canonical event type.
- Use `event["attributes"]["event.name"]` as the short event name when present.
- Prefer `attributes["event.timestamp"]` as event time; retain `logEvents[].timestamp` as ingestion metadata.
- Treat attributes as an untrusted string map until the normalization layer coerces types.
- Keep malformed rows visible through validation errors or quarantine records instead of silently dropping them.

Known event bodies:

- `claude_code.user_prompt`
- `claude_code.api_request`
- `claude_code.api_error`
- `claude_code.tool_decision`
- `claude_code.tool_result`

## Event Fields

Common attributes usually include:

- `event.timestamp`
- `event.name`
- `organization.id`
- `session.id`
- `terminal.type`
- `user.account_uuid`
- `user.email`
- `user.id`

Resource fields usually include:

- `host.arch`
- `host.name`
- `os.type`
- `os.version`
- `service.name`
- `service.version`
- `user.email`
- `user.practice`
- `user.profile`
- `user.serial`

Event-specific attributes:

- `api_request`: `model`, `cost_usd`, `duration_ms`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`.
- `api_error`: `model`, `status_code`, `error`, `duration_ms`, `attempt`.
- `tool_decision`: `tool_name`, `decision`, `source`.
- `tool_result`: `tool_name`, `decision_type`, `decision_source`, `success`, `duration_ms`, optional `tool_result_size_bytes`.
- `user_prompt`: `prompt`, `prompt_length`; prompt contents are redacted.

## Normalized Model

Preserve raw records and expose typed analytical tables or equivalent models.

Recommended entities:

- `raw_log_batches`: one row per JSONL line with batch metadata and raw JSON.
- `raw_log_events`: one row per `logEvents[]` item with `id`, epoch timestamp, partition date, and raw nested message.
- `events`: one row per parsed event with common fields and raw `attributes_json`/`resource_json`.
- `api_requests`: typed request metrics.
- `api_errors`: typed API error metrics.
- `tool_decisions`: typed tool permission decisions.
- `tool_results`: typed tool execution outcomes.
- `user_prompts`: typed prompt metadata.
- `employees`: CSV enrichment keyed by `email`.

Common event columns:

```text
event_id
event_type
event_name
event_timestamp_utc
session_id
organization_id
user_email
user_id
user_account_uuid
terminal_type
scope_name
scope_version
host_arch
host_name
os_type
os_version
service_name
service_version
user_profile
user_serial
attributes_json
resource_json
```

Type coercion:

- Parse timestamps as UTC-aware datetimes.
- Parse token counts, durations, attempts, and byte sizes as integers.
- Parse `cost_usd` as decimal or float with consistent rounding for display.
- Parse `success` from lowercase string booleans.
- Keep status codes as strings for grouping unless numeric comparisons are needed.

## Expected Metrics

Compute metrics that support product and operational decisions:

- Adoption: active users, sessions, prompts, usage by practice, level, and location.
- Engagement: sessions per user, prompts per session, events per session, session duration, turns per session when inferable.
- Cost and tokens: total cost, cost per user/session/model, input/output tokens, cache read/create tokens, cache efficiency.
- Model usage: request count, cost, token volume, latency, and error rate by model.
- Tool usage: decision counts, accept/reject rate, source mix, result success rate, duration, output size.
- Reliability: API error count/rate, status code mix, retry attempts, failed tools, slow requests/tools.
- Environment: usage by Claude Code version, terminal type, OS, architecture, and service version.
- Time trends: daily or weekly movement in users, sessions, prompts, requests, cost, tokens, latency, and errors.

Prefer metrics with clear denominators. Label rates precisely, for example `api_errors / api_requests`, `accepted_tool_decisions / tool_decisions`, or `successful_tool_results / tool_results`.

## Dashboard Guidance

Build dashboards for scanning and drill-down:

- Executive/product overview: active users, sessions, prompts, cost, tokens, model mix, top trends.
- Engineering usage: practice/level/location cohorts, engagement distribution, heavy users, session depth.
- Operations/reliability: errors, latency, status codes, failed tools, version and environment breakdowns.
- Cost optimization: model spend, cache tokens, cost per request/session/user, high-cost outliers.

Make every visual traceable to a metric function or query. Avoid charts that cannot be explained from normalized data.

## Coding Conventions

- Separate ingestion, normalization, metrics, and presentation layers.
- Prefer small pure functions for parsers and metric calculations.
- Validate inputs at boundaries and return structured errors where practical.
- Preserve raw payloads for debugging.
- Use deterministic seeds and small fixtures for tests.
- Do not commit generated large datasets, API keys, tokens, or credentials.
- Provide `.env.example` if environment variables are introduced.
- Maintain one primary command to start the finished app.

## Testing Expectations

Cover:

- JSONL line parsing.
- Nested `logEvents[].message` JSON parsing.
- Missing or malformed batch/message handling.
- Common field extraction.
- Event-specific type coercion.
- Employee enrichment by email.
- Metrics on deterministic fixtures with hand-checkable expected values.
- App/API/dashboard smoke paths after UI code exists.

## Commands

Generate realistic data:

```bash
python3 claude_code_telemetry/generate_fake_data.py --num-users 100 --num-sessions 5000 --days 60 --output-dir data/raw --seed 42
```

Generate a small fixture:

```bash
python3 claude_code_telemetry/generate_fake_data.py --num-users 5 --num-sessions 20 --days 7 --output-dir data/sample --seed 7
```

Validate this skill:

```bash
python3 /Users/oscarsegura/.codex/skills/.system/skill-creator/scripts/quick_validate.py .codex/skills/telemetry-analysis
```
