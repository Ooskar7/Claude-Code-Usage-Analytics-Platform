from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


Row = dict[str, Any]


@dataclass(frozen=True)
class MetricFilters:
    start_date: date | None = None
    end_date: date | None = None
    practices: tuple[str, ...] = field(default_factory=tuple)
    levels: tuple[str, ...] = field(default_factory=tuple)
    locations: tuple[str, ...] = field(default_factory=tuple)
    models: tuple[str, ...] = field(default_factory=tuple)

    def cache_key(self) -> tuple[Any, ...]:
        return (
            self.start_date.isoformat() if self.start_date else None,
            self.end_date.isoformat() if self.end_date else None,
            self.practices,
            self.levels,
            self.locations,
            self.models,
        )


def fetch_all(conn: Any, sql: str, params: list[Any] | None = None) -> list[Row]:
    cursor = conn.execute(sql, params or [])
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def fetch_one(conn: Any, sql: str, params: list[Any] | None = None) -> Row:
    cursor = conn.execute(sql, params or [])
    columns = [column[0] for column in cursor.description]
    row = cursor.fetchone()
    if row is None:
        return {}
    return dict(zip(columns, row, strict=True))


def _as_tuple(values: tuple[str, ...] | list[str] | None) -> tuple[str, ...]:
    return tuple(value for value in (values or ()) if value)


def filter_where(filters: MetricFilters | None = None, *, include_model: bool = True) -> tuple[str, list[Any]]:
    filters = filters or MetricFilters()
    conditions = ["e.event_timestamp_utc IS NOT NULL"]
    params: list[Any] = []

    if filters.start_date is not None:
        conditions.append("cast(e.event_timestamp_utc AS DATE) >= ?")
        params.append(filters.start_date)
    if filters.end_date is not None:
        conditions.append("cast(e.event_timestamp_utc AS DATE) <= ?")
        params.append(filters.end_date)

    dimension_filters = [
        ("emp.practice", _as_tuple(filters.practices)),
        ("emp.level", _as_tuple(filters.levels)),
        ("emp.location", _as_tuple(filters.locations)),
    ]
    for column, values in dimension_filters:
        if values:
            conditions.append(f"{column} IN ({', '.join(['?'] * len(values))})")
            params.extend(values)

    models = _as_tuple(filters.models)
    if include_model and models:
        conditions.append(
            """
            e.session_id IN (
                SELECT DISTINCT model_events.session_id
                FROM events model_events
                LEFT JOIN api_requests model_requests
                    ON model_events.event_id = model_requests.event_id
                LEFT JOIN api_errors model_errors
                    ON model_events.event_id = model_errors.event_id
                WHERE model_requests.model IN ({placeholders})
                    OR model_errors.model IN ({placeholders})
            )
            """.format(placeholders=", ".join(["?"] * len(models)))
        )
        params.extend(models)
        params.extend(models)

    return "WHERE " + " AND ".join(conditions), params


def filtered_events_cte(filters: MetricFilters | None = None, *, include_model: bool = True) -> tuple[str, list[Any]]:
    where_clause, params = filter_where(filters, include_model=include_model)
    return (
        f"""
        WITH filtered_events AS (
            SELECT DISTINCT e.*
            FROM events e
            LEFT JOIN employees emp ON e.user_email = emp.email
            LEFT JOIN api_requests ar ON e.event_id = ar.event_id
            LEFT JOIN api_errors ae ON e.event_id = ae.event_id
            {where_clause}
        )
        """,
        params,
    )


def filtered_event_ids_cte(filters: MetricFilters | None = None, *, include_model: bool = True) -> tuple[str, list[Any]]:
    cte, params = filtered_events_cte(filters, include_model=include_model)
    return (
        cte
        + """
        , filtered_event_ids AS (
            SELECT event_id FROM filtered_events
        )
        """,
        params,
    )


def available_filter_options(conn: Any) -> Row:
    return {
        "date_range": fetch_one(
            conn,
            """
            SELECT
                min(cast(event_timestamp_utc AS DATE)) AS min_date,
                max(cast(event_timestamp_utc AS DATE)) AS max_date
            FROM events
            WHERE event_timestamp_utc IS NOT NULL;
            """,
        ),
        "practices": [
            row["practice"]
            for row in fetch_all(
                conn,
                """
                SELECT DISTINCT practice
                FROM employees
                WHERE practice IS NOT NULL AND practice != ''
                ORDER BY practice;
                """,
            )
        ],
        "levels": [
            row["level"]
            for row in fetch_all(
                conn,
                """
                SELECT DISTINCT level
                FROM employees
                WHERE level IS NOT NULL AND level != ''
                ORDER BY level;
                """,
            )
        ],
        "locations": [
            row["location"]
            for row in fetch_all(
                conn,
                """
                SELECT DISTINCT location
                FROM employees
                WHERE location IS NOT NULL AND location != ''
                ORDER BY location;
                """,
            )
        ],
        "models": [
            row["model"]
            for row in fetch_all(
                conn,
                """
                SELECT model
                FROM (
                    SELECT DISTINCT model FROM api_requests WHERE model IS NOT NULL
                    UNION
                    SELECT DISTINCT model FROM api_errors WHERE model IS NOT NULL
                )
                ORDER BY model;
                """,
            )
        ],
    }


def overview_kpis(conn: Any, filters: MetricFilters | None = None) -> Row:
    cte, params = filtered_event_ids_cte(filters)
    return fetch_one(
        conn,
        cte
        + """
        , totals AS (
            SELECT
                count(DISTINCT user_email) AS active_users,
                count(DISTINCT session_id) AS sessions,
                count(*) AS total_events,
                count(*) FILTER (WHERE event_type = 'claude_code.user_prompt') AS prompts
            FROM filtered_events
        ),
        request_totals AS (
            SELECT
                count(*) AS api_requests,
                coalesce(sum(cost_usd), 0) AS total_cost_usd,
                coalesce(sum(input_tokens), 0) AS input_tokens,
                coalesce(sum(output_tokens), 0) AS output_tokens,
                coalesce(sum(cache_read_tokens), 0) AS cache_read_tokens,
                coalesce(sum(cache_creation_tokens), 0) AS cache_creation_tokens
            FROM api_requests
            WHERE event_id IN (SELECT event_id FROM filtered_event_ids)
        ),
        error_totals AS (
            SELECT count(*) AS api_errors
            FROM api_errors
            WHERE event_id IN (SELECT event_id FROM filtered_event_ids)
        ),
        tool_decision_totals AS (
            SELECT
                count(*) AS tool_decisions,
                count(*) FILTER (WHERE decision = 'accept') AS accepted_tool_decisions
            FROM tool_decisions
            WHERE event_id IN (SELECT event_id FROM filtered_event_ids)
        ),
        tool_result_totals AS (
            SELECT
                count(*) AS tool_results,
                count(*) FILTER (WHERE success) AS successful_tool_results
            FROM tool_results
            WHERE event_id IN (SELECT event_id FROM filtered_event_ids)
        )
        SELECT
            totals.active_users,
            totals.sessions,
            totals.total_events,
            totals.prompts,
            request_totals.api_requests,
            error_totals.api_errors,
            request_totals.total_cost_usd,
            request_totals.input_tokens,
            request_totals.output_tokens,
            request_totals.cache_read_tokens,
            request_totals.cache_creation_tokens,
            request_totals.input_tokens + request_totals.output_tokens
                + request_totals.cache_read_tokens + request_totals.cache_creation_tokens
                AS total_tokens,
            request_totals.total_cost_usd / nullif(totals.active_users, 0) AS cost_usd_per_active_user,
            request_totals.total_cost_usd / nullif(totals.sessions, 0) AS cost_usd_per_session,
            totals.prompts::DOUBLE / nullif(totals.sessions, 0) AS prompts_per_session,
            totals.total_events::DOUBLE / nullif(totals.sessions, 0) AS events_per_session,
            error_totals.api_errors::DOUBLE / nullif(request_totals.api_requests, 0)
                AS api_error_rate_api_errors_per_api_request,
            tool_decision_totals.accepted_tool_decisions::DOUBLE
                / nullif(tool_decision_totals.tool_decisions, 0)
                AS accepted_tool_decisions_per_tool_decision,
            tool_result_totals.successful_tool_results::DOUBLE
                / nullif(tool_result_totals.tool_results, 0)
                AS successful_tool_results_per_tool_result
        FROM totals
        CROSS JOIN request_totals
        CROSS JOIN error_totals
        CROSS JOIN tool_decision_totals
        CROSS JOIN tool_result_totals;
        """,
        params,
    )


def daily_usage_trends(conn: Any, filters: MetricFilters | None = None) -> list[Row]:
    cte, params = filtered_event_ids_cte(filters)
    return fetch_all(
        conn,
        cte
        + """
        SELECT
            cast(e.event_timestamp_utc AS DATE) AS event_date,
            count(DISTINCT e.user_email) AS active_users,
            count(DISTINCT e.session_id) AS sessions,
            count(*) AS total_events,
            count(*) FILTER (WHERE e.event_type = 'claude_code.user_prompt') AS prompts,
            count(*) FILTER (WHERE e.event_type = 'claude_code.api_request') AS api_requests,
            count(*) FILTER (WHERE e.event_type = 'claude_code.api_error') AS api_errors,
            coalesce(sum(ar.cost_usd), 0) AS total_cost_usd,
            coalesce(sum(
                ar.input_tokens + ar.output_tokens
                + ar.cache_read_tokens + ar.cache_creation_tokens
            ), 0) AS total_tokens
        FROM filtered_events e
        LEFT JOIN api_requests ar ON e.event_id = ar.event_id
        GROUP BY 1
        ORDER BY 1;
        """,
        params,
    )


def active_users_and_sessions(conn: Any, filters: MetricFilters | None = None) -> Row:
    cte, params = filtered_events_cte(filters)
    return fetch_one(
        conn,
        cte
        + """
        , session_bounds AS (
            SELECT
                session_id,
                user_email,
                min(event_timestamp_utc) AS session_start_utc,
                max(event_timestamp_utc) AS session_end_utc,
                date_diff('millisecond', min(event_timestamp_utc), max(event_timestamp_utc))
                    AS session_duration_ms
            FROM filtered_events
            WHERE session_id IS NOT NULL
            GROUP BY 1, 2
        )
        SELECT
            count(DISTINCT user_email) AS active_users,
            count(*) AS sessions,
            count(*)::DOUBLE / nullif(count(DISTINCT user_email), 0) AS sessions_per_active_user,
            avg(session_duration_ms) AS avg_session_duration_ms,
            median(session_duration_ms) AS median_session_duration_ms,
            max(session_duration_ms) AS max_session_duration_ms
        FROM session_bounds;
        """,
        params,
    )


def prompt_metrics(conn: Any, filters: MetricFilters | None = None) -> Row:
    cte, params = filtered_event_ids_cte(filters)
    return fetch_one(
        conn,
        cte
        + """
        SELECT
            count(*) AS prompts,
            min(prompt_length) AS min_prompt_length,
            avg(prompt_length) AS avg_prompt_length,
            median(prompt_length) AS median_prompt_length,
            quantile_cont(prompt_length, 0.9) AS p90_prompt_length,
            max(prompt_length) AS max_prompt_length
        FROM user_prompts
        WHERE event_id IN (SELECT event_id FROM filtered_event_ids);
        """,
        params,
    )


def cost_token_totals(conn: Any, filters: MetricFilters | None = None) -> Row:
    cte, params = filtered_event_ids_cte(filters)
    return fetch_one(
        conn,
        cte
        + """
        SELECT
            count(*) AS api_requests,
            coalesce(sum(cost_usd), 0) AS total_cost_usd,
            coalesce(sum(input_tokens), 0) AS input_tokens,
            coalesce(sum(output_tokens), 0) AS output_tokens,
            coalesce(sum(cache_read_tokens), 0) AS cache_read_tokens,
            coalesce(sum(cache_creation_tokens), 0) AS cache_creation_tokens,
            coalesce(sum(input_tokens + output_tokens + cache_read_tokens + cache_creation_tokens), 0)
                AS total_tokens,
            coalesce(sum(cost_usd), 0) / nullif(count(*), 0) AS cost_usd_per_api_request,
            coalesce(sum(cache_read_tokens), 0)::DOUBLE
                / nullif(sum(input_tokens + output_tokens + cache_read_tokens + cache_creation_tokens), 0)
                AS cache_read_tokens_per_total_token
        FROM api_requests
        WHERE event_id IN (SELECT event_id FROM filtered_event_ids);
        """,
        params,
    )


def model_usage(conn: Any, filters: MetricFilters | None = None) -> list[Row]:
    cte, params = filtered_event_ids_cte(filters)
    return fetch_all(
        conn,
        cte
        + """
        , request_metrics AS (
            SELECT
                model,
                count(*) AS api_requests,
                sum(cost_usd) AS total_cost_usd,
                avg(duration_ms) AS avg_request_duration_ms,
                median(duration_ms) AS median_request_duration_ms,
                quantile_cont(duration_ms, 0.9) AS p90_request_duration_ms,
                sum(input_tokens) AS input_tokens,
                sum(output_tokens) AS output_tokens,
                sum(cache_read_tokens) AS cache_read_tokens,
                sum(cache_creation_tokens) AS cache_creation_tokens,
                sum(input_tokens + output_tokens + cache_read_tokens + cache_creation_tokens)
                    AS total_tokens
            FROM api_requests
            WHERE event_id IN (SELECT event_id FROM filtered_event_ids)
            GROUP BY 1
        ),
        error_metrics AS (
            SELECT model, count(*) AS api_errors
            FROM api_errors
            WHERE event_id IN (SELECT event_id FROM filtered_event_ids)
            GROUP BY 1
        )
        SELECT
            rm.model,
            rm.api_requests,
            coalesce(em.api_errors, 0) AS api_errors,
            coalesce(em.api_errors, 0)::DOUBLE / nullif(rm.api_requests, 0)
                AS api_error_rate_api_errors_per_api_request,
            rm.total_cost_usd,
            rm.total_cost_usd / nullif(rm.api_requests, 0) AS cost_usd_per_api_request,
            rm.avg_request_duration_ms,
            rm.median_request_duration_ms,
            rm.p90_request_duration_ms,
            rm.input_tokens,
            rm.output_tokens,
            rm.cache_read_tokens,
            rm.cache_creation_tokens,
            rm.total_tokens
        FROM request_metrics rm
        LEFT JOIN error_metrics em ON rm.model = em.model
        ORDER BY rm.total_cost_usd DESC, rm.api_requests DESC;
        """,
        params,
    )


def usage_by_practice(conn: Any, filters: MetricFilters | None = None) -> list[Row]:
    return usage_by_employee_dimension(conn, "practice", filters)


def usage_by_level(conn: Any, filters: MetricFilters | None = None) -> list[Row]:
    return usage_by_employee_dimension(conn, "level", filters)


def usage_by_location(conn: Any, filters: MetricFilters | None = None) -> list[Row]:
    return usage_by_employee_dimension(conn, "location", filters)


def usage_by_employee_dimension(
    conn: Any,
    dimension: str,
    filters: MetricFilters | None = None,
) -> list[Row]:
    allowed = {"practice", "level", "location"}
    if dimension not in allowed:
        raise ValueError(f"unsupported employee dimension: {dimension}")

    cte, params = filtered_events_cte(filters)
    return fetch_all(
        conn,
        cte
        + f"""
        SELECT
            coalesce(emp.{dimension}, 'Unknown') AS {dimension},
            count(DISTINCT e.user_email) AS active_users,
            count(DISTINCT e.session_id) AS sessions,
            count(*) FILTER (WHERE e.event_type = 'claude_code.user_prompt') AS prompts,
            count(ar.event_id) AS api_requests,
            coalesce(sum(ar.cost_usd), 0) AS total_cost_usd,
            coalesce(sum(
                ar.input_tokens + ar.output_tokens
                + ar.cache_read_tokens + ar.cache_creation_tokens
            ), 0) AS total_tokens,
            count(*) FILTER (WHERE e.event_type = 'claude_code.user_prompt')::DOUBLE
                / nullif(count(DISTINCT e.session_id), 0) AS prompts_per_session
        FROM filtered_events e
        LEFT JOIN employees emp ON e.user_email = emp.email
        LEFT JOIN api_requests ar ON e.event_id = ar.event_id
        GROUP BY 1
        ORDER BY active_users DESC, sessions DESC;
        """,
        params,
    )


def tool_usage(conn: Any, filters: MetricFilters | None = None) -> list[Row]:
    cte, params = filtered_event_ids_cte(filters)
    return fetch_all(
        conn,
        cte
        + """
        , decisions AS (
            SELECT
                tool_name,
                count(*) AS tool_decisions,
                count(*) FILTER (WHERE decision = 'accept') AS accepted_tool_decisions,
                count(*) FILTER (WHERE decision = 'reject') AS rejected_tool_decisions
            FROM tool_decisions
            WHERE event_id IN (SELECT event_id FROM filtered_event_ids)
            GROUP BY 1
        ),
        results AS (
            SELECT
                tool_name,
                count(*) AS tool_results,
                count(*) FILTER (WHERE success) AS successful_tool_results,
                avg(duration_ms) AS avg_tool_duration_ms,
                median(duration_ms) AS median_tool_duration_ms,
                quantile_cont(duration_ms, 0.9) AS p90_tool_duration_ms,
                avg(tool_result_size_bytes) AS avg_tool_result_size_bytes
            FROM tool_results
            WHERE event_id IN (SELECT event_id FROM filtered_event_ids)
            GROUP BY 1
        )
        SELECT
            coalesce(d.tool_name, r.tool_name) AS tool_name,
            coalesce(d.tool_decisions, 0) AS tool_decisions,
            coalesce(d.accepted_tool_decisions, 0) AS accepted_tool_decisions,
            coalesce(d.rejected_tool_decisions, 0) AS rejected_tool_decisions,
            d.accepted_tool_decisions::DOUBLE / nullif(d.tool_decisions, 0)
                AS accepted_tool_decisions_per_tool_decision,
            coalesce(r.tool_results, 0) AS tool_results,
            coalesce(r.successful_tool_results, 0) AS successful_tool_results,
            r.successful_tool_results::DOUBLE / nullif(r.tool_results, 0)
                AS successful_tool_results_per_tool_result,
            r.avg_tool_duration_ms,
            r.median_tool_duration_ms,
            r.p90_tool_duration_ms,
            r.avg_tool_result_size_bytes
        FROM decisions d
        FULL OUTER JOIN results r ON d.tool_name = r.tool_name
        ORDER BY tool_decisions DESC, tool_results DESC;
        """,
        params,
    )


def api_error_summary(conn: Any, filters: MetricFilters | None = None) -> Row:
    cte, params = filtered_event_ids_cte(filters)
    return fetch_one(
        conn,
        cte
        + """
        , request_count AS (
            SELECT count(*) AS api_requests
            FROM api_requests
            WHERE event_id IN (SELECT event_id FROM filtered_event_ids)
        ),
        error_count AS (
            SELECT
                count(*) AS api_errors,
                avg(duration_ms) AS avg_error_duration_ms,
                max(attempt) AS max_retry_attempt
            FROM api_errors
            WHERE event_id IN (SELECT event_id FROM filtered_event_ids)
        )
        SELECT
            ec.api_errors,
            rc.api_requests,
            ec.api_errors::DOUBLE / nullif(rc.api_requests, 0)
                AS api_error_rate_api_errors_per_api_request,
            ec.avg_error_duration_ms,
            ec.max_retry_attempt
        FROM error_count ec
        CROSS JOIN request_count rc;
        """,
        params,
    )


def api_error_status_code_mix(conn: Any, filters: MetricFilters | None = None) -> list[Row]:
    cte, params = filtered_event_ids_cte(filters)
    return fetch_all(
        conn,
        cte
        + """
        , error_count AS (
            SELECT count(*) AS api_errors
            FROM api_errors
            WHERE event_id IN (SELECT event_id FROM filtered_event_ids)
        )
        SELECT
            status_code,
            count(*) AS api_errors,
            count(*)::DOUBLE / nullif((SELECT api_errors FROM error_count), 0)
                AS status_code_share_of_api_errors,
            avg(duration_ms) AS avg_error_duration_ms,
            max(attempt) AS max_retry_attempt
        FROM api_errors
        WHERE event_id IN (SELECT event_id FROM filtered_event_ids)
        GROUP BY 1
        ORDER BY api_errors DESC, status_code;
        """,
        params,
    )


def api_error_model_breakdown(conn: Any, filters: MetricFilters | None = None) -> list[Row]:
    cte, params = filtered_event_ids_cte(filters)
    return fetch_all(
        conn,
        cte
        + """
        , request_metrics AS (
            SELECT model, count(*) AS api_requests
            FROM api_requests
            WHERE event_id IN (SELECT event_id FROM filtered_event_ids)
            GROUP BY 1
        ),
        error_metrics AS (
            SELECT
                model,
                count(*) AS api_errors,
                avg(duration_ms) AS avg_error_duration_ms,
                max(attempt) AS max_retry_attempt
            FROM api_errors
            WHERE event_id IN (SELECT event_id FROM filtered_event_ids)
            GROUP BY 1
        )
        SELECT
            coalesce(rm.model, em.model) AS model,
            coalesce(rm.api_requests, 0) AS api_requests,
            coalesce(em.api_errors, 0) AS api_errors,
            coalesce(em.api_errors, 0)::DOUBLE / nullif(rm.api_requests, 0)
                AS api_error_rate_api_errors_per_api_request,
            em.avg_error_duration_ms,
            em.max_retry_attempt
        FROM request_metrics rm
        FULL OUTER JOIN error_metrics em ON rm.model = em.model
        ORDER BY api_errors DESC, api_requests DESC;
        """,
        params,
    )


def api_error_metrics(conn: Any, filters: MetricFilters | None = None) -> Row:
    return {
        "summary": api_error_summary(conn, filters),
        "status_code_mix": api_error_status_code_mix(conn, filters),
        "model_breakdown": api_error_model_breakdown(conn, filters),
    }


def environment_breakdown(conn: Any, filters: MetricFilters | None = None) -> Row:
    return {
        "terminal_type": environment_dimension(conn, "terminal_type", filters),
        "os_type": environment_dimension(conn, "os_type", filters),
        "service_version": environment_dimension(conn, "service_version", filters),
    }


def environment_dimension(conn: Any, dimension: str, filters: MetricFilters | None = None) -> list[Row]:
    allowed = {"terminal_type", "os_type", "service_version"}
    if dimension not in allowed:
        raise ValueError(f"unsupported environment dimension: {dimension}")

    cte, params = filtered_events_cte(filters)
    return fetch_all(
        conn,
        cte
        + f"""
        SELECT
            coalesce({dimension}, 'Unknown') AS {dimension},
            count(DISTINCT user_email) AS active_users,
            count(DISTINCT session_id) AS sessions,
            count(*) AS total_events,
            count(*) FILTER (WHERE event_type = 'claude_code.user_prompt') AS prompts
        FROM filtered_events
        GROUP BY 1
        ORDER BY active_users DESC, total_events DESC;
        """,
        params,
    )
