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
from telemetry_analytics.metrics.queries import DAILY_PRODUCT_TREND_SQL


st.set_page_config(page_title="Product Overview", page_icon=":bar_chart:", layout="wide")
st.title("Product Overview")

settings = get_settings()
if not database_exists(settings.db_path):
    st.info("No DuckDB warehouse found.")
    st.stop()

with connect(settings.db_path, read_only=True) as conn:
    trend = conn.execute(DAILY_PRODUCT_TREND_SQL).fetchdf()

st.line_chart(
    trend,
    x="event_date",
    y=["active_users", "sessions", "prompts"],
    use_container_width=True,
)
st.dataframe(trend, use_container_width=True, hide_index=True)
