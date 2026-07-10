PYTHON ?= python3
STREAMLIT ?= streamlit
DB_PATH ?= data/processed/telemetry.duckdb
RAW_DIR ?= data/raw
SAMPLE_DIR ?= data/sample

.DEFAULT_GOAL := help

.PHONY: help install-deps check-deps demo demo-data dev init-db ingest ingest-sample generate-data sample-data realistic-data test lint format clean-data

help:
	@echo "Claude Code telemetry analytics commands"
	@echo ""
	@echo "  make install-deps   Install runtime and test dependencies"
	@echo "  make demo           Check deps, create sample data if missing, refresh DuckDB, start Streamlit"
	@echo "  make demo-data      Check deps, create sample data if missing, refresh DuckDB"
	@echo "  make sample-data    Generate deterministic small sample data in data/sample"
	@echo "  make realistic-data Generate realistic local data in data/raw"
	@echo "  make ingest         Refresh DuckDB from data/raw"
	@echo "  make ingest-sample  Refresh DuckDB from data/sample"
	@echo "  make test           Run the deterministic test suite"
	@echo "  make clean-data     Remove generated data and local DuckDB files"

install-deps:
	$(PYTHON) -m pip install -e ".[dev]"

check-deps:
	$(PYTHON) -c "import duckdb, plotly, pytest, streamlit"

demo: demo-data dev

demo-data: check-deps $(SAMPLE_DIR)/telemetry_logs.jsonl $(SAMPLE_DIR)/employees.csv ingest-sample

dev: check-deps
	PYTHONPATH=src TELEMETRY_DB_PATH=$(DB_PATH) $(STREAMLIT) run app/Home.py

init-db:
	PYTHONPATH=src TELEMETRY_DB_PATH=$(DB_PATH) $(PYTHON) -m telemetry_analytics.cli init-db --db-path $(DB_PATH)

ingest:
	PYTHONPATH=src $(PYTHON) -m telemetry_analytics.cli ingest --telemetry-path $(RAW_DIR)/telemetry_logs.jsonl --employees-path $(RAW_DIR)/employees.csv --db-path $(DB_PATH)

ingest-sample:
	PYTHONPATH=src $(PYTHON) -m telemetry_analytics.cli ingest --telemetry-path $(SAMPLE_DIR)/telemetry_logs.jsonl --employees-path $(SAMPLE_DIR)/employees.csv --db-path $(DB_PATH)

generate-data: sample-data realistic-data

sample-data:
	$(PYTHON) claude_code_telemetry/generate_fake_data.py --num-users 5 --num-sessions 20 --days 7 --output-dir $(SAMPLE_DIR) --seed 7

$(SAMPLE_DIR)/telemetry_logs.jsonl $(SAMPLE_DIR)/employees.csv:
	$(MAKE) sample-data

realistic-data:
	$(PYTHON) claude_code_telemetry/generate_fake_data.py --num-users 100 --num-sessions 5000 --days 60 --output-dir $(RAW_DIR) --seed 42

test:
	PYTHONPATH=src $(PYTHON) -m pytest

lint:
	PYTHONPATH=src ruff check .

format:
	ruff format .

clean-data:
	rm -f $(RAW_DIR)/telemetry_logs.jsonl $(RAW_DIR)/employees.csv
	rm -f $(SAMPLE_DIR)/telemetry_logs.jsonl $(SAMPLE_DIR)/employees.csv
	rm -f $(DB_PATH) $(DB_PATH).wal data/warehouse/*.duckdb data/warehouse/*.duckdb.wal
