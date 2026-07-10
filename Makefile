PYTHON ?= python3
STREAMLIT ?= streamlit
DB_PATH ?= data/processed/telemetry.duckdb
RAW_DIR ?= data/raw
SAMPLE_DIR ?= data/sample

.PHONY: dev init-db ingest ingest-sample generate-data sample-data realistic-data test lint format

dev:
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

realistic-data:
	$(PYTHON) claude_code_telemetry/generate_fake_data.py --num-users 100 --num-sessions 5000 --days 60 --output-dir $(RAW_DIR) --seed 42

test:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -p 'test_*.py'

lint:
	PYTHONPATH=src ruff check .

format:
	ruff format .
