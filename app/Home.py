from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from telemetry_analytics.config import get_settings
from telemetry_analytics.db import connect, database_exists, table_exists
from telemetry_analytics.metrics.duckdb_metrics import (
    active_users_and_sessions,
    api_error_metrics,
    cost_token_totals,
    daily_usage_trends,
    environment_breakdown,
    model_usage,
    overview_kpis,
    prompt_metrics,
    tool_usage,
    usage_by_level,
    usage_by_location,
    usage_by_practice,
)


st.set_page_config(page_title="Claude Code Telemetry", page_icon=":bar_chart:", layout="wide")


def fmt_int(value: Any) -> str:
    if value is None:
        return "0"
    return f"{int(value):,}"


def fmt_float(value: Any, digits: int = 2) -> str:
    if value is None:
        return "0"
    return f"{float(value):,.{digits}f}"


def fmt_money(value: Any) -> str:
    return f"${fmt_float(value, 2)}"


def fmt_pct(value: Any) -> str:
    if value is None:
        return "0.0%"
    return f"{float(value) * 100:.1f}%"


def fmt_duration_ms(value: Any) -> str:
    if value is None:
        return "0s"
    seconds = float(value) / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{seconds / 60:.1f}m"


def values(rows: list[dict[str, Any]], key: str) -> list[Any]:
    return [row.get(key) for row in rows]


def bar_chart(
    rows: list[dict[str, Any]],
    *,
    x: str,
    y: str,
    title: str,
    x_title: str | None = None,
    y_title: str | None = None,
    orientation: str = "v",
) -> go.Figure:
    if orientation == "h":
        fig = go.Figure(go.Bar(x=values(rows, y), y=values(rows, x), orientation="h"))
        fig.update_layout(yaxis={"autorange": "reversed"})
    else:
        fig = go.Figure(go.Bar(x=values(rows, x), y=values(rows, y)))
    fig.update_layout(
        title=title,
        xaxis_title=x_title or x.replace("_", " ").title(),
        yaxis_title=y_title or y.replace("_", " ").title(),
        margin={"l": 20, "r": 20, "t": 48, "b": 20},
        height=340,
    )
    return fig


def line_chart(
    rows: list[dict[str, Any]],
    *,
    x: str,
    y_columns: list[str],
    title: str,
    y_title: str,
) -> go.Figure:
    fig = go.Figure()
    for column in y_columns:
        fig.add_trace(
            go.Scatter(
                x=values(rows, x),
                y=values(rows, column),
                mode="lines+markers",
                name=column.replace("_", " ").title(),
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title=x.replace("_", " ").title(),
        yaxis_title=y_title,
        margin={"l": 20, "r": 20, "t": 48, "b": 20},
        height=340,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    return fig


def stacked_bar_chart(
    rows: list[dict[str, Any]],
    *,
    x: str,
    y_columns: list[str],
    title: str,
    y_title: str,
) -> go.Figure:
    fig = go.Figure()
    for column in y_columns:
        fig.add_trace(go.Bar(x=values(rows, x), y=values(rows, column), name=column.replace("_", " ").title()))
    fig.update_layout(
        barmode="stack",
        title=title,
        xaxis_title=x.replace("_", " ").title(),
        yaxis_title=y_title,
        margin={"l": 20, "r": 20, "t": 48, "b": 20},
        height=360,
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "right", "x": 1},
    )
    return fig


def table(rows: list[dict[str, Any]], *, height: int = 320) -> None:
    st.dataframe(rows, width="stretch", hide_index=True, height=height)


def chart_source(function_name: str) -> None:
    st.caption(f"Source: `telemetry_analytics.metrics.duckdb_metrics.{function_name}`")


@st.cache_data(show_spinner=False)
def load_dashboard_metrics(db_path: str) -> dict[str, Any]:
    with connect(db_path, read_only=True) as conn:
        if not table_exists(conn, "events"):
            return {"has_events": False}

        kpis = overview_kpis(conn)
        if not kpis or not kpis.get("total_events"):
            return {"has_events": False}

        return {
            "has_events": True,
            "overview": kpis,
            "daily_usage_trends": daily_usage_trends(conn),
            "active_users_and_sessions": active_users_and_sessions(conn),
            "prompt_metrics": prompt_metrics(conn),
            "cost_token_totals": cost_token_totals(conn),
            "model_usage": model_usage(conn),
            "usage_by_practice": usage_by_practice(conn),
            "usage_by_level": usage_by_level(conn),
            "usage_by_location": usage_by_location(conn),
            "tool_usage": tool_usage(conn),
            "api_error_metrics": api_error_metrics(conn),
            "environment_breakdown": environment_breakdown(conn),
        }


def show_missing_database(db_path: Path) -> None:
    st.info("No DuckDB database found for the dashboard.")
    st.code(
        f"make sample-data\nmake ingest-sample\n\n# or load the realistic dataset\nmake realistic-data\nmake ingest\n\n# expected path\n{db_path}",
        language="bash",
    )


def show_empty_database(db_path: Path) -> None:
    st.info("The DuckDB database exists, but normalized telemetry rows are not loaded yet.")
    st.code(f"make ingest-sample\n\n# current database\n{db_path}", language="bash")


settings = get_settings()

with st.sidebar:
    st.header("Warehouse")
    st.code(str(settings.db_path), language="text")
    if st.button("Refresh dashboard data", width="stretch"):
        load_dashboard_metrics.clear()
    st.divider()
    st.caption("All charts use the DuckDB metric/query layer.")

st.title("Claude Code Telemetry")
st.caption("Interactive usage, cost, reliability, tool, and environment analytics from normalized telemetry.")

if not database_exists(settings.db_path):
    show_missing_database(settings.db_path)
    st.stop()

try:
    metrics = load_dashboard_metrics(str(settings.db_path))
except Exception as exc:
    st.error("The dashboard could not read the DuckDB database.")
    st.exception(exc)
    st.stop()

if not metrics.get("has_events"):
    show_empty_database(settings.db_path)
    st.stop()

overview = metrics["overview"]
daily = metrics["daily_usage_trends"]
models = metrics["model_usage"]
tools = metrics["tool_usage"]
errors = metrics["api_error_metrics"]
environment = metrics["environment_breakdown"]

tabs = st.tabs(["Overview", "Model Usage", "Team/User Insights", "Tool Behavior", "Reliability", "Environment"])

with tabs[0]:
    st.subheader("Overview")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Active users", fmt_int(overview["active_users"]))
    k2.metric("Sessions", fmt_int(overview["sessions"]))
    k3.metric("Prompts", fmt_int(overview["prompts"]))
    k4.metric("API requests", fmt_int(overview["api_requests"]))
    k5.metric("API cost", fmt_money(overview["total_cost_usd"]))
    k6.metric("Total tokens", fmt_int(overview["total_tokens"]))

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Prompts / session", fmt_float(overview["prompts_per_session"], 1))
    r2.metric("Events / session", fmt_float(overview["events_per_session"], 1))
    r3.metric("API errors / requests", fmt_pct(overview["api_error_rate_api_errors_per_api_request"]))
    r4.metric("Tool successes / results", fmt_pct(overview["successful_tool_results_per_tool_result"]))

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            line_chart(
                daily,
                x="event_date",
                y_columns=["active_users", "sessions", "prompts"],
                title="Daily adoption and prompt activity",
                y_title="Count",
            ),
            width="stretch",
        )
        chart_source("daily_usage_trends")
    with c2:
        st.plotly_chart(
            line_chart(
                daily,
                x="event_date",
                y_columns=["total_cost_usd", "api_errors"],
                title="Daily cost and API errors",
                y_title="Value",
            ),
            width="stretch",
        )
        chart_source("daily_usage_trends")

    st.subheader("Session and prompt profile")
    session_metrics = metrics["active_users_and_sessions"]
    prompt_stats = metrics["prompt_metrics"]
    cost_tokens = metrics["cost_token_totals"]
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Sessions / active user", fmt_float(session_metrics["sessions_per_active_user"], 2))
    s2.metric("Average session", fmt_duration_ms(session_metrics["avg_session_duration_ms"]))
    s3.metric("Median prompt length", fmt_int(prompt_stats["median_prompt_length"]))
    s4.metric("Cache read / all tokens", fmt_pct(cost_tokens["cache_read_tokens_per_total_token"]))

with tabs[1]:
    st.subheader("Model Usage")
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            bar_chart(
                models[:10],
                x="model",
                y="total_cost_usd",
                title="Model spend",
                y_title="Cost USD",
            ),
            width="stretch",
        )
        chart_source("model_usage")
    with c2:
        st.plotly_chart(
            bar_chart(
                models[:10],
                x="model",
                y="p90_request_duration_ms",
                title="P90 request latency by model",
                y_title="Milliseconds",
            ),
            width="stretch",
        )
        chart_source("model_usage")

    st.plotly_chart(
        stacked_bar_chart(
            models,
            x="model",
            y_columns=["input_tokens", "output_tokens", "cache_read_tokens", "cache_creation_tokens"],
            title="Token mix by model",
            y_title="Tokens",
        ),
        width="stretch",
    )
    chart_source("model_usage")
    table(models)

with tabs[2]:
    st.subheader("Team/User Insights")
    by_practice = metrics["usage_by_practice"]
    by_level = metrics["usage_by_level"]
    by_location = metrics["usage_by_location"]
    c1, c2, c3 = st.columns(3)
    with c1:
        st.plotly_chart(
            bar_chart(
                by_practice,
                x="practice",
                y="active_users",
                title="Active users by practice",
                y_title="Active users",
            ),
            width="stretch",
        )
        chart_source("usage_by_practice")
    with c2:
        st.plotly_chart(
            bar_chart(
                by_level,
                x="level",
                y="sessions",
                title="Sessions by level",
                y_title="Sessions",
            ),
            width="stretch",
        )
        chart_source("usage_by_level")
    with c3:
        st.plotly_chart(
            bar_chart(
                by_location,
                x="location",
                y="total_cost_usd",
                title="Cost by location",
                y_title="Cost USD",
            ),
            width="stretch",
        )
        chart_source("usage_by_location")

    st.subheader("Cohort tables")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("Practice")
        table(by_practice, height=260)
    with c2:
        st.caption("Level")
        table(by_level, height=260)
    with c3:
        st.caption("Location")
        table(by_location, height=260)

with tabs[3]:
    st.subheader("Tool Behavior")
    top_tools = tools[:12]
    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            bar_chart(
                top_tools,
                x="tool_name",
                y="tool_decisions",
                title="Tool decision volume",
                y_title="Tool decisions",
                orientation="h",
            ),
            width="stretch",
        )
        chart_source("tool_usage")
    with c2:
        st.plotly_chart(
            bar_chart(
                top_tools,
                x="tool_name",
                y="successful_tool_results_per_tool_result",
                title="Tool success rate",
                y_title="Successful tool results / tool results",
                orientation="h",
            ),
            width="stretch",
        )
        chart_source("tool_usage")

    st.plotly_chart(
        bar_chart(
            top_tools,
            x="tool_name",
            y="p90_tool_duration_ms",
            title="P90 tool duration",
            y_title="Milliseconds",
            orientation="h",
        ),
        width="stretch",
    )
    chart_source("tool_usage")
    table(tools)

with tabs[4]:
    st.subheader("Reliability")
    error_summary = errors["summary"]
    e1, e2, e3, e4 = st.columns(4)
    e1.metric("API errors", fmt_int(error_summary["api_errors"]))
    e2.metric("API requests", fmt_int(error_summary["api_requests"]))
    e3.metric("API errors / requests", fmt_pct(error_summary["api_error_rate_api_errors_per_api_request"]))
    e4.metric("Max retry attempt", fmt_int(error_summary["max_retry_attempt"]))

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(
            bar_chart(
                errors["status_code_mix"],
                x="status_code",
                y="api_errors",
                title="API errors by status code",
                y_title="API errors",
            ),
            width="stretch",
        )
        chart_source("api_error_status_code_mix")
    with c2:
        st.plotly_chart(
            bar_chart(
                errors["model_breakdown"],
                x="model",
                y="api_error_rate_api_errors_per_api_request",
                title="API error rate by model",
                y_title="API errors / API requests",
            ),
            width="stretch",
        )
        chart_source("api_error_model_breakdown")

    table(errors["model_breakdown"])

with tabs[5]:
    st.subheader("Environment")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.plotly_chart(
            bar_chart(
                environment["terminal_type"],
                x="terminal_type",
                y="sessions",
                title="Sessions by terminal",
                y_title="Sessions",
            ),
            width="stretch",
        )
        chart_source("environment_breakdown")
    with c2:
        st.plotly_chart(
            bar_chart(
                environment["os_type"],
                x="os_type",
                y="active_users",
                title="Active users by OS",
                y_title="Active users",
            ),
            width="stretch",
        )
        chart_source("environment_breakdown")
    with c3:
        st.plotly_chart(
            bar_chart(
                environment["service_version"][:10],
                x="service_version",
                y="total_events",
                title="Events by service version",
                y_title="Events",
            ),
            width="stretch",
        )
        chart_source("environment_breakdown")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.caption("Terminal type")
        table(environment["terminal_type"], height=260)
    with c2:
        st.caption("Operating system")
        table(environment["os_type"], height=260)
    with c3:
        st.caption("Service version")
        table(environment["service_version"], height=260)
