# Claude Code Telemetry Analytics

Streamlit and DuckDB analytics platform for nested Claude Code telemetry logs.

## Current Startup Command

```bash
make dev
```

The app reads `TELEMETRY_DB_PATH`, defaulting to `data/warehouse/telemetry.duckdb`. Initialize an empty DuckDB warehouse with:

```bash
make init-db
```

## Dataset Commands

Generate a deterministic fixture-sized dataset:

```bash
make sample-data
```

Generate a realistic local dataset:

```bash
make realistic-data
```

Generated telemetry files are intentionally ignored by Git. Keep small deterministic fixtures under `tests/fixtures/` when tests need committed data.

## Project Structure

```text
app/                         Streamlit dashboard entrypoint and pages
sql/schema.sql               DuckDB normalized table contract
src/telemetry_analytics/     Ingestion, normalization, metrics, and DB code
tests/                       Focused parser/model contract tests
data/raw/                    Large generated local telemetry data
data/sample/                 Small generated local telemetry data
data/warehouse/              Local DuckDB files
```

The normalized model preserves raw records before coercion and exposes typed analytical tables:

- `raw_log_batches`
- `raw_log_events`
- `events`
- `api_requests`
- `api_errors`
- `tool_decisions`
- `tool_results`
- `user_prompts`
- `employees`

## Development

```bash
make test
make lint
```

Install the dependencies from `pyproject.toml` in a virtual environment before running Streamlit or DuckDB commands.
