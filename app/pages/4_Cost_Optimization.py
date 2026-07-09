from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from telemetry_analytics.config import get_settings
from telemetry_analytics.db import connect, database_exists
from telemetry_analytics.metrics.queries import MODEL_COST_SQL


st.set_page_config(page_title="Cost Optimization", page_icon=":bar_chart:", layout="wide")
st.title("Cost Optimization")

settings = get_settings()
if not database_exists(settings.db_path):
    st.info("No DuckDB warehouse found.")
    st.stop()

with connect(settings.db_path, read_only=True) as conn:
    model_cost = conn.execute(MODEL_COST_SQL).fetchdf()

st.bar_chart(model_cost, x="model", y="cost_usd", use_container_width=True)
st.dataframe(model_cost, use_container_width=True, hide_index=True)
