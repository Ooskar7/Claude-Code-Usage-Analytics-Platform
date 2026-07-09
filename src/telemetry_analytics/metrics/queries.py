OVERVIEW_KPIS_SQL = """
SELECT
    count(DISTINCT e.user_email) AS active_users,
    count(DISTINCT e.session_id) AS sessions,
    count(*) FILTER (WHERE e.event_type = 'claude_code.user_prompt') AS prompts,
    coalesce(sum(ar.cost_usd), 0) AS cost_usd,
    coalesce(sum(ar.input_tokens + ar.output_tokens + ar.cache_read_tokens + ar.cache_creation_tokens), 0) AS tokens
FROM events e
LEFT JOIN api_requests ar ON e.event_id = ar.event_id;
"""

DAILY_PRODUCT_TREND_SQL = """
SELECT
    cast(event_timestamp_utc AS DATE) AS event_date,
    count(DISTINCT user_email) AS active_users,
    count(DISTINCT session_id) AS sessions,
    count(*) FILTER (WHERE event_type = 'claude_code.user_prompt') AS prompts
FROM events
WHERE event_timestamp_utc IS NOT NULL
GROUP BY 1
ORDER BY 1;
"""

ENGINEERING_COHORT_SQL = """
SELECT
    coalesce(emp.practice, 'Unknown') AS practice,
    coalesce(emp.level, 'Unknown') AS level,
    coalesce(emp.location, 'Unknown') AS location,
    count(DISTINCT e.user_email) AS active_users,
    count(DISTINCT e.session_id) AS sessions,
    count(*) FILTER (WHERE e.event_type = 'claude_code.user_prompt') AS prompts
FROM events e
LEFT JOIN employees emp ON e.user_email = emp.email
GROUP BY 1, 2, 3
ORDER BY active_users DESC, sessions DESC;
"""

RELIABILITY_SQL = """
WITH request_count AS (
    SELECT count(*) AS api_requests FROM api_requests
),
error_count AS (
    SELECT
        status_code,
        count(*) AS api_errors,
        avg(duration_ms) AS avg_error_duration_ms,
        max(attempt) AS max_attempt
    FROM api_errors
    GROUP BY 1
)
SELECT
    ec.status_code,
    ec.api_errors,
    rc.api_requests,
    ec.api_errors::DOUBLE / nullif(rc.api_requests, 0) AS api_error_rate,
    ec.avg_error_duration_ms,
    ec.max_attempt
FROM error_count ec
CROSS JOIN request_count rc
ORDER BY api_errors DESC;
"""

MODEL_COST_SQL = """
SELECT
    model,
    count(*) AS requests,
    sum(cost_usd) AS cost_usd,
    avg(duration_ms) AS avg_duration_ms,
    sum(input_tokens) AS input_tokens,
    sum(output_tokens) AS output_tokens,
    sum(cache_read_tokens) AS cache_read_tokens,
    sum(cache_creation_tokens) AS cache_creation_tokens
FROM api_requests
GROUP BY 1
ORDER BY cost_usd DESC;
"""
