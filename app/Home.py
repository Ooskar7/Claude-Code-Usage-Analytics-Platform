from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from telemetry_analytics.config import get_settings
from telemetry_analytics.db import connect, database_exists, initialize_schema
from telemetry_analytics.metrics.queries import OVERVIEW_KPIS_SQL


st.set_page_config(
    page_title="Claude Code Telemetry",
    page_icon=":bar_chart:",
    layout="wide",
)

settings = get_settings()

st.title("Claude Code Telemetry")
st.caption("Product, engineering, operations, and cost analytics from normalized usage events.")

with st.sidebar:
    st.subheader("Warehouse")
    st.code(str(settings.db_path), language="text")
    initialize = st.button("Initialize schema", use_container_width=True)

if initialize:
    with connect(settings.db_path) as conn:
        initialize_schema(conn)
    st.success("DuckDB schema initialized.")

if not database_exists(settings.db_path):
    st.info("No DuckDB warehouse found. Run `make init-db`, then load generated telemetry.")
    st.stop()

with connect(settings.db_path, read_only=True) as conn:
    kpis = conn.execute(OVERVIEW_KPIS_SQL).fetchdf()

if kpis.empty:
    st.info("The warehouse is initialized but contains no normalized events yet.")
    st.stop()

row = kpis.iloc[0]
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Active users", f"{int(row['active_users']):,}")
col2.metric("Sessions", f"{int(row['sessions']):,}")
col3.metric("Prompts", f"{int(row['prompts']):,}")
col4.metric("API cost", f"${float(row['cost_usd'] or 0):,.2f}")
col5.metric("Tokens", f"{int(row['tokens'] or 0):,}")

st.divider()
st.subheader("Normalized Tables")
st.dataframe(kpis, use_container_width=True, hide_index=True)
