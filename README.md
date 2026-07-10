# Claude Code Telemetry Analytics

Streamlit and DuckDB analytics platform for synthetic Claude Code telemetry. The app ingests nested JSONL log batches, normalizes event records into analytical tables, computes product and engineering metrics, and presents an operational dashboard for product, engineering leadership, and reliability users.

## Assignment Context

This project is an internship analytics assignment. The goal is to build an end-to-end platform that can:

- process Claude Code telemetry data,
- preserve raw records for traceability,
- normalize typed event tables,
- enrich events with employee metadata,
- compute actionable usage, cost, tool, reliability, and environment metrics,
- present interactive dashboards,
- include a reproducible tuned agent setup.

The repository includes the required agent setup:

- [AGENTS.md](AGENTS.md): root project instructions and data contract.
- [.codex/skills/telemetry-analysis/SKILL.md](.codex/skills/telemetry-analysis/SKILL.md): custom Codex skill used to guide parsing, normalization, metrics, testing, and dashboard work.

No secrets or external APIs are required.

## Quick Start

Install dependencies once from a fresh checkout:

```bash
make install-deps
```

Run the full local demo:

```bash
make demo
```

`make demo` checks dependencies, generates deterministic sample data if missing, refreshes `data/processed/telemetry.duckdb`, and starts the Streamlit dashboard.

Open the dashboard at the URL printed by Streamlit, usually:

```text
http://localhost:8501
```

## Command Reference

```bash
make help
```

Primary commands:

```bash
make install-deps   # Install runtime and test dependencies
make demo           # Prepare sample data + DuckDB, then start Streamlit
make demo-data      # Prepare sample data + DuckDB without starting Streamlit
make test           # Run deterministic pytest suite
make clean-data     # Remove generated local data and DuckDB files
```

Data and ingestion commands:

```bash
make sample-data      # Generate small deterministic sample dataset, seed 7
make realistic-data   # Generate larger local dataset, seed 42
make generate-data    # Generate both sample and realistic datasets
make ingest-sample    # Refresh DuckDB from data/sample
make ingest           # Refresh DuckDB from data/raw
make init-db          # Create an empty DuckDB schema
```

## Architecture Overview

```text
claude_code_telemetry/generate_fake_data.py
  -> data/sample or data/raw
       telemetry_logs.jsonl      employees.csv
              |                       |
              v                       v
       ingestion.parser          ingestion.employees
              |                       |
              v                       |
       normalize.telemetry <-----------
              |
              v
       storage.duckdb_store
              |
              v
       data/processed/telemetry.duckdb
              |
              v
       metrics.duckdb_metrics
              |
              v
       app/Home.py Streamlit dashboard
```

Layer responsibilities:

- `ingestion`: parses JSONL batches and employee CSVs, collects parse and validation errors.
- `normalize`: extracts common event fields, event-specific typed rows, and raw trace payloads.
- `storage`: recreates or refreshes the DuckDB database idempotently.
- `metrics`: exposes reusable DuckDB-backed metric functions independent of Streamlit.
- `app`: renders the operational dashboard using the metric layer.

## Data Generation

The source generator is [claude_code_telemetry/generate_fake_data.py](claude_code_telemetry/generate_fake_data.py). It uses only the Python standard library.

Small deterministic dataset:

```bash
make sample-data
```

Writes:

- `data/sample/telemetry_logs.jsonl`
- `data/sample/employees.csv`

Realistic local dataset:

```bash
make realistic-data
```

Writes:

- `data/raw/telemetry_logs.jsonl`
- `data/raw/employees.csv`

Generated data and DuckDB files are ignored by Git. Small committed fixtures live under `tests/fixtures/`.

## Ingestion And Normalization

Telemetry JSONL is nested. Each line is a batch, not a single event:

```text
JSONL line
  batch object
    logEvents[]
      id
      timestamp
      message: JSON string
        body
        attributes
        scope
        resource
```

Parsing rules implemented by the loader:

- Parse each JSONL line as a batch.
- Validate `batch["logEvents"]`.
- Iterate each log event.
- Parse `log_event["message"]` as nested JSON.
- Use `message["body"]` as canonical event type.
- Use `attributes["event.name"]` as the short event name.
- Prefer `attributes["event.timestamp"]` for event time.
- Preserve raw batch, log event, attributes, resource, and message payloads for debugging.

Type coercion happens at the normalization boundary:

- timestamps -> UTC-aware datetimes,
- tokens, durations, attempts, byte sizes -> integers,
- cost -> float,
- success strings -> booleans.

Validation is non-fatal. Bad records are quarantined through collected error lists and `raw_log_events.parse_status` values such as `parse_error`, `validation_error`, or `normalization_error`.

## DuckDB Schema Summary

The schema lives in [sql/schema.sql](sql/schema.sql). Core tables:

- `raw_log_batches`: one row per JSONL batch line with source file, line number, partition fields, and raw JSON.
- `raw_log_events`: one row per log event with ingestion timestamp, batch date, raw log event JSON, raw parsed message JSON, and parse status.
- `events`: common typed event fields for all telemetry events.
- `api_requests`: model, cost, duration, input/output tokens, cache read/create tokens.
- `api_errors`: model, status code, error text, duration, retry attempt.
- `tool_decisions`: tool name, decision, decision source.
- `tool_results`: tool name, decision metadata, success, duration, optional result size.
- `user_prompts`: redacted prompt marker and prompt length.
- `employees`: employee enrichment keyed by email.

The database is stored at:

```text
data/processed/telemetry.duckdb
```

## Dashboard

The dashboard entry point is [app/Home.py](app/Home.py).

Sections:

- Overview: active users, sessions, prompts, requests, cost, tokens, trends.
- Model Usage: spend, latency, token mix, model-level error rate.
- Team/User Insights: usage by practice, level, and location.
- Tool Behavior: tool decision volume, acceptance rate, success rate, duration.
- Reliability: API errors, error rate, status code mix, model breakdown.
- Environment: terminal, OS, and service version distribution.

Global filters:

- date range,
- practice,
- level,
- location,
- model.

Charts and tables are backed by functions in [src/telemetry_analytics/metrics/duckdb_metrics.py](src/telemetry_analytics/metrics/duckdb_metrics.py). The UI does not contain complex SQL.

## Metric Definitions

Metric functions use explicit denominators in names and labels.

Adoption and engagement:

- `active_users`: distinct `events.user_email`.
- `sessions`: distinct `events.session_id`.
- `prompts`: count of `claude_code.user_prompt` events.
- `sessions_per_active_user`: sessions / active users.
- `prompts_per_session`: prompts / sessions.
- `events_per_session`: all events / sessions.
- session duration: max event time - min event time per session.

Cost and tokens:

- `total_cost_usd`: sum of `api_requests.cost_usd`.
- `total_tokens`: input + output + cache read + cache creation tokens.
- `cost_usd_per_api_request`: total cost / API requests.
- `cost_usd_per_session`: total cost / sessions.
- `cache_read_tokens_per_total_token`: cache read tokens / total tokens.

Model usage:

- `api_requests`: request count by model.
- `total_cost_usd`: model spend.
- `avg_request_duration_ms`, `median_request_duration_ms`, `p90_request_duration_ms`.
- token mix: input, output, cache read, cache creation.
- `api_error_rate_api_errors_per_api_request`: model API errors / model API requests.

Tool behavior:

- `tool_decisions`: permission decision count.
- `accepted_tool_decisions_per_tool_decision`: accepted decisions / all decisions.
- `successful_tool_results_per_tool_result`: successful results / all tool results.
- tool duration: average, median, and p90 milliseconds.

Reliability:

- `api_errors`: API error count.
- `api_error_rate_api_errors_per_api_request`: API errors / API requests.
- status code mix: status-code errors / all API errors.
- retry attempt: max attempt observed in `api_errors`.

Environment:

- active users, sessions, events, and prompts by terminal type, OS type, and service version.

## Testing

Run all tests:

```bash
make test
```

The suite uses deterministic fixtures and covers:

- JSONL batch parsing,
- nested message parsing,
- malformed line and missing `logEvents` handling,
- missing input files,
- missing required common fields,
- numeric and timestamp coercion failures,
- employee enrichment mismatches,
- DuckDB schema and idempotent ingestion,
- metric calculations and filters,
- dashboard-supporting metric smoke paths.

Optional linting:

```bash
make lint
```

## Agent Setup

The assignment explicitly evaluates tuned agent usage. This repository keeps the agent setup as committed project context:

- `AGENTS.md` defines the project goal, dataset contract, normalized model, metric expectations, commands, and testing expectations.
- `.codex/skills/telemetry-analysis/SKILL.md` gives Codex task-specific parsing, normalization, metric, dashboard, and testing instructions.

The application code follows those contracts. README claims are tied to implemented modules, schema, tests, and Makefile commands.

Validate the local skill definition:

```bash
python3 /Users/oscarsegura/.codex/skills/.system/skill-creator/scripts/quick_validate.py .codex/skills/telemetry-analysis
```

## Limitations

- The default demo uses synthetic sample data, not real production telemetry.
- The larger generated dataset can be hundreds of MB and is intentionally not committed.
- DuckDB is local-file based; there is no multi-user warehouse, scheduler, or deployment packaging yet.
- Dashboard filters are global and operational; there is no row-level security or authentication.
- Prompt contents are redacted by design, so prompt analysis is limited to prompt counts and lengths.
- Cost values are synthetic and should be interpreted as simulated spend.

## Future Improvements

- Add deployment packaging with Docker Compose.
- Add incremental ingestion keyed by source file and batch ID.
- Add materialized aggregate tables for very large generated datasets.
- Add anomaly detection for cost, latency, and error spikes.
- Add dashboard export or reporting snapshots.
- Add CI for tests, linting, and skill validation.
