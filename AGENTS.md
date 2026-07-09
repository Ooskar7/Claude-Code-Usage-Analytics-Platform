# Agent Setup: Claude Code Telemetry Analytics

## Assignment Goal

Build an end-to-end analytics platform for Claude Code telemetry data. The solution must ingest nested JSONL logs, normalize events, compute product and engineering usage metrics, and present clear interactive dashboards for product, engineering leadership, and operations users.

This repository intentionally includes a tuned agent setup before application code:

- Root agent instructions: `AGENTS.md`
- Custom Codex skill: `.codex/skills/telemetry-analysis/SKILL.md`

Use the local `$telemetry-analysis` skill for data ingestion, normalization, analytics, dashboard, test, and documentation work.

## Dataset Structure

Source files live under `claude_code_telemetry/`.

- `generate_fake_data.py`: standard-library Python generator for synthetic telemetry.
- `README.md`: dataset description and generator options.
- Generated `telemetry_logs.jsonl`: one CloudWatch-style batch per line.
- Generated `employees.csv`: employee enrichment keyed by `email`.

Employee columns:

- `email`
- `full_name`
- `practice`
- `level`
- `location`

## Nested JSONL Log Shape

Do not treat each JSONL line as a single event. Each line is a batch:

```text
telemetry_logs.jsonl line
  batch object
    logEvents[]
      id
      timestamp
      message: JSON-encoded string
        body
        attributes
        scope
        resource
```

Parsing rules:

- Parse each line as JSON.
- Iterate `batch.logEvents`.
- Parse each `logEvents[].message` as JSON.
- Use `message.body` as the canonical event type.
- Use `message.attributes["event.name"]` as the short event name when present.
- Prefer `attributes["event.timestamp"]` for event time; retain `logEvents[].timestamp` for ingestion/debugging.
- Treat numeric fields in `attributes` as strings until explicitly coerced.

Known event bodies:

- `claude_code.user_prompt`
- `claude_code.api_request`
- `claude_code.api_error`
- `claude_code.tool_decision`
- `claude_code.tool_result`

## Normalized Data Model

Use a normalized model that preserves raw data and exposes typed analytical entities.

Recommended core tables or equivalent in-memory models:

- `raw_log_batches`: batch metadata and original JSON for traceability.
- `raw_log_events`: `log_event_id`, batch date partition, epoch timestamp, and raw `message`.
- `events`: common typed fields for every telemetry event.
- `api_requests`: model, token counts, cache tokens, cost, duration.
- `api_errors`: model, status code, error text, duration, attempt.
- `tool_decisions`: tool name, decision, source.
- `tool_results`: tool name, decision type/source, success, duration, optional result size.
- `user_prompts`: redacted prompt marker and prompt length.
- `employees`: employee enrichment from `employees.csv`.

Common `events` fields:

- `event_id`
- `event_type`
- `event_name`
- `event_timestamp_utc`
- `session_id`
- `organization_id`
- `user_email`
- `user_id`
- `user_account_uuid`
- `terminal_type`
- `scope_name`
- `scope_version`
- `host_arch`
- `host_name`
- `os_type`
- `os_version`
- `service_name`
- `service_version`
- `user_profile`
- `user_serial`
- `attributes_json`
- `resource_json`

## Expected Metrics

At minimum, compute metrics in these categories:

- Adoption: active users, sessions, prompts, usage by practice, level, and location.
- Engagement: sessions per user, prompts per session, events per session, session duration.
- Cost and tokens: cost USD, input/output tokens, cache read/create tokens, cost per user/session/model.
- Model usage: request counts, cost, latency, and token mix by model.
- Tool usage: tool decision counts, acceptance/rejection rate, result success rate, duration, output size.
- Reliability: API error counts, error rate, status code mix, retry attempts, failed tool results.
- Environment: usage by Claude Code version, terminal type, operating system, and host architecture.
- Time trends: daily/weekly trends for usage, cost, tokens, latency, and errors.

Prefer actionable dashboard views over vanity aggregates. Every chart should answer a product or operational question.

## Coding Conventions

- Keep ingestion, normalization, metric computation, and UI code separated.
- Preserve raw records before coercion so parsing bugs can be debugged.
- Use UTC-aware timestamps end to end.
- Convert numeric string attributes at the normalization boundary.
- Make transformations deterministic and testable with small fixtures.
- Validate required fields and handle malformed JSONL lines or bad nested messages without crashing the full run.
- Avoid committing generated data unless it is a small fixture.
- Never commit secrets. Use environment variables and provide `.env.example` for any required configuration.
- Prefer a single documented startup command for the final app, such as `docker compose up` or `make dev`.
- Keep README and presentation claims tied to metrics produced by the code.

## Testing Expectations

Add focused tests for:

- JSONL batch loading and nested `message` parsing.
- Malformed line, missing `logEvents`, and invalid nested message handling.
- Type coercion for cost, duration, tokens, success booleans, and timestamps.
- Employee enrichment by email.
- Metric calculations on deterministic synthetic fixtures.
- Dashboard/API smoke paths after the app exists.

Use the generator seed for reproducible local data. Tests should not depend on large generated datasets.

## Commands To Run

Generate a realistic local dataset:

```bash
python3 claude_code_telemetry/generate_fake_data.py --num-users 100 --num-sessions 5000 --days 60 --output-dir data/raw --seed 42
```

Generate a small fixture-sized dataset:

```bash
python3 claude_code_telemetry/generate_fake_data.py --num-users 5 --num-sessions 20 --days 7 --output-dir data/sample --seed 7
```

Validate the custom skill after edits:

```bash
python3 /Users/oscarsegura/.codex/skills/.system/skill-creator/scripts/quick_validate.py .codex/skills/telemetry-analysis
```

When application code is added, document and maintain one primary startup command plus test/lint commands here and in `README.md`.
