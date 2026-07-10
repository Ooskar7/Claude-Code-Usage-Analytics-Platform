# Architecture

The telemetry platform is organized as four layers.

## Ingestion

`telemetry_analytics.ingestion` parses JSONL batches in two stages:

1. Parse each line as a CloudWatch-style batch.
2. Iterate `batch["logEvents"]` and parse each `message` string as a telemetry event.

Malformed lines, missing `logEvents`, and invalid nested messages are represented as structured parser errors so they can be quarantined instead of silently dropped.

## Normalization

`telemetry_analytics.normalize` turns untrusted string attributes into typed rows. Common event fields land in `events`; body-specific metrics land in `api_requests`, `api_errors`, `tool_decisions`, `tool_results`, and `user_prompts`.

Raw data remains available in `raw_log_batches`, `raw_log_events`, `attributes_json`, and `resource_json`.

## Storage

DuckDB is the local warehouse. The schema contract lives in `sql/schema.sql` and mirrors the normalized model described by `AGENTS.md` and the `telemetry-analysis` skill.

## Metrics

`telemetry_analytics.metrics.duckdb_metrics` contains reusable DuckDB-backed metric functions. Functions return plain Python dictionaries or lists of dictionaries, keep rate denominators explicit in metric names, and do not depend on Streamlit.

## Presentation

Streamlit pages are grouped by decision audience:

- Product overview
- Engineering usage
- Reliability operations
- Cost optimization

Each page imports SQL from `telemetry_analytics.metrics.queries` so visualizations remain traceable to query definitions.
