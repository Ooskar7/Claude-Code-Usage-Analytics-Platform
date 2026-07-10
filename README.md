# Claude Code Telemetry Analytics

Streamlit and DuckDB analytics platform for nested Claude Code telemetry logs.

## One-Command Demo

```bash
make demo
```

`make demo` checks Python dependencies, generates the deterministic sample dataset if it is missing, refreshes `data/processed/telemetry.duckdb`, and starts the Streamlit dashboard.

From a fresh checkout, install dependencies once first:

```bash
make install-deps
```

No secrets or external APIs are required.

## Supporting Commands

The app reads `TELEMETRY_DB_PATH`, defaulting to `data/processed/telemetry.duckdb`. Initialize an empty DuckDB warehouse with:

```bash
make init-db
```

Load generated telemetry into DuckDB:

```bash
make ingest
```

For faster local verification against the small generated dataset:

```bash
make ingest-sample
```

Prepare sample data and DuckDB without starting Streamlit:

```bash
make demo-data
```

Remove generated data and local DuckDB files:

```bash
make clean-data
```

## Dataset Commands

Generate both local datasets:

```bash
make generate-data
```

Generate a deterministic fixture-sized dataset in `data/sample` with seed `7`:

```bash
make sample-data
```

This writes:

- `data/sample/telemetry_logs.jsonl`
- `data/sample/employees.csv`

Generate a realistic local dataset in `data/raw` with seed `42`:

```bash
make realistic-data
```

This writes:

- `data/raw/telemetry_logs.jsonl`
- `data/raw/employees.csv`

Generated telemetry files are intentionally ignored by Git. Keep small deterministic fixtures under `tests/fixtures/` when tests need committed data.

## Project Structure

```text
app/                         Streamlit dashboard entrypoint and pages
sql/schema.sql               DuckDB normalized table contract
src/telemetry_analytics/     Ingestion, normalization, metrics, and DB code
tests/                       Focused parser/model contract tests
data/raw/                    Large generated local telemetry data
data/sample/                 Small generated local telemetry data
data/processed/              Local DuckDB files
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
