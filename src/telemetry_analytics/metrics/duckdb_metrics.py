from __future__ import annotations

from typing import Any


Row = dict[str, Any]


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


def overview_kpis(conn: Any) -> Row:
    return fetch_one(
        conn,
        """
        WITH totals AS (
            SELECT
                count(DISTINCT user_email) AS active_users,
                count(DISTINCT session_id) AS sessions,
                count(*) AS total_events,
                count(*) FILTER (WHERE event_type = 'claude_code.user_prompt') AS prompts
            FROM events
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
        ),
        error_totals AS (
            SELECT count(*) AS api_errors
            FROM api_errors
        ),
        tool_decision_totals AS (
            SELECT
                count(*) AS tool_decisions,
                count(*) FILTER (WHERE decision = 'accept') AS accepted_tool_decisions
            FROM tool_decisions
        ),
        tool_result_totals AS (
            SELECT
                count(*) AS tool_results,
                count(*) FILTER (WHERE success) AS successful_tool_results
            FROM tool_results
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
    )


def daily_usage_trends(conn: Any) -> list[Row]:
    return fetch_all(
        conn,
        """
        SELECT
            cast(event_timestamp_utc AS DATE) AS event_date,
            count(DISTINCT user_email) AS active_users,
            count(DISTINCT session_id) AS sessions,
            count(*) AS total_events,
            count(*) FILTER (WHERE event_type = 'claude_code.user_prompt') AS prompts,
            count(*) FILTER (WHERE event_type = 'claude_code.api_request') AS api_requests,
            count(*) FILTER (WHERE event_type = 'claude_code.api_error') AS api_errors,
            coalesce(sum(ar.cost_usd), 0) AS total_cost_usd,
            coalesce(sum(
                ar.input_tokens + ar.output_tokens
                + ar.cache_read_tokens + ar.cache_creation_tokens
            ), 0) AS total_tokens
        FROM events e
        LEFT JOIN api_requests ar ON e.event_id = ar.event_id
        WHERE event_timestamp_utc IS NOT NULL
        GROUP BY 1
        ORDER BY 1;
        """,
    )


def active_users_and_sessions(conn: Any) -> Row:
    return fetch_one(
        conn,
        """
        WITH session_bounds AS (
            SELECT
                session_id,
                user_email,
                min(event_timestamp_utc) AS session_start_utc,
                max(event_timestamp_utc) AS session_end_utc,
                date_diff('millisecond', min(event_timestamp_utc), max(event_timestamp_utc))
                    AS session_duration_ms
            FROM events
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
    )


def prompt_metrics(conn: Any) -> Row:
    return fetch_one(
        conn,
        """
        SELECT
            count(*) AS prompts,
            min(prompt_length) AS min_prompt_length,
            avg(prompt_length) AS avg_prompt_length,
            median(prompt_length) AS median_prompt_length,
            quantile_cont(prompt_length, 0.9) AS p90_prompt_length,
            max(prompt_length) AS max_prompt_length
        FROM user_prompts;
        """,
    )


def cost_token_totals(conn: Any) -> Row:
    return fetch_one(
        conn,
        """
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
        FROM api_requests;
        """,
    )


def model_usage(conn: Any) -> list[Row]:
    return fetch_all(
        conn,
        """
        WITH request_metrics AS (
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
            GROUP BY 1
        ),
        error_metrics AS (
            SELECT model, count(*) AS api_errors
            FROM api_errors
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
    )


def usage_by_practice(conn: Any) -> list[Row]:
    return usage_by_employee_dimension(conn, "practice")


def usage_by_level(conn: Any) -> list[Row]:
    return usage_by_employee_dimension(conn, "level")


def usage_by_location(conn: Any) -> list[Row]:
    return usage_by_employee_dimension(conn, "location")


def usage_by_employee_dimension(conn: Any, dimension: str) -> list[Row]:
    allowed = {"practice", "level", "location"}
    if dimension not in allowed:
        raise ValueError(f"unsupported employee dimension: {dimension}")

    return fetch_all(
        conn,
        f"""
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
        FROM events e
        LEFT JOIN employees emp ON e.user_email = emp.email
        LEFT JOIN api_requests ar ON e.event_id = ar.event_id
        GROUP BY 1
        ORDER BY active_users DESC, sessions DESC;
        """,
    )


def tool_usage(conn: Any) -> list[Row]:
    return fetch_all(
        conn,
        """
        WITH decisions AS (
            SELECT
                tool_name,
                count(*) AS tool_decisions,
                count(*) FILTER (WHERE decision = 'accept') AS accepted_tool_decisions,
                count(*) FILTER (WHERE decision = 'reject') AS rejected_tool_decisions
            FROM tool_decisions
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
    )


def api_error_summary(conn: Any) -> Row:
    return fetch_one(
        conn,
        """
        WITH request_count AS (
            SELECT count(*) AS api_requests FROM api_requests
        ),
        error_count AS (
            SELECT
                count(*) AS api_errors,
                avg(duration_ms) AS avg_error_duration_ms,
                max(attempt) AS max_retry_attempt
            FROM api_errors
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
    )


def api_error_status_code_mix(conn: Any) -> list[Row]:
    return fetch_all(
        conn,
        """
        WITH error_count AS (
            SELECT count(*) AS api_errors FROM api_errors
        )
        SELECT
            status_code,
            count(*) AS api_errors,
            count(*)::DOUBLE / nullif((SELECT api_errors FROM error_count), 0)
                AS status_code_share_of_api_errors,
            avg(duration_ms) AS avg_error_duration_ms,
            max(attempt) AS max_retry_attempt
        FROM api_errors
        GROUP BY 1
        ORDER BY api_errors DESC, status_code;
        """,
    )


def api_error_model_breakdown(conn: Any) -> list[Row]:
    return fetch_all(
        conn,
        """
        WITH request_metrics AS (
            SELECT model, count(*) AS api_requests
            FROM api_requests
            GROUP BY 1
        ),
        error_metrics AS (
            SELECT
                model,
                count(*) AS api_errors,
                avg(duration_ms) AS avg_error_duration_ms,
                max(attempt) AS max_retry_attempt
            FROM api_errors
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
    )


def api_error_metrics(conn: Any) -> Row:
    return {
        "summary": api_error_summary(conn),
        "status_code_mix": api_error_status_code_mix(conn),
        "model_breakdown": api_error_model_breakdown(conn),
    }


def environment_breakdown(conn: Any) -> Row:
    return {
        "terminal_type": environment_dimension(conn, "terminal_type"),
        "os_type": environment_dimension(conn, "os_type"),
        "service_version": environment_dimension(conn, "service_version"),
    }


def environment_dimension(conn: Any, dimension: str) -> list[Row]:
    allowed = {"terminal_type", "os_type", "service_version"}
    if dimension not in allowed:
        raise ValueError(f"unsupported environment dimension: {dimension}")

    return fetch_all(
        conn,
        f"""
        SELECT
            coalesce({dimension}, 'Unknown') AS {dimension},
            count(DISTINCT user_email) AS active_users,
            count(DISTINCT session_id) AS sessions,
            count(*) AS total_events,
            count(*) FILTER (WHERE event_type = 'claude_code.user_prompt') AS prompts
        FROM events
        GROUP BY 1
        ORDER BY active_users DESC, total_events DESC;
        """,
    )
