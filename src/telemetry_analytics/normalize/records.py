from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


JsonObject = dict[str, Any]


def clean_mapping(value: Any) -> JsonObject:
    return value if isinstance(value, dict) else {}


def as_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def parse_utc_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def parse_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def parse_bool(value: Any) -> bool | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"invalid boolean value: {value!r}")


def normalize_common_event(event_id: str, log_event_id: str, message: JsonObject) -> JsonObject:
    attributes = clean_mapping(message.get("attributes"))
    resource = clean_mapping(message.get("resource"))
    scope = clean_mapping(message.get("scope"))

    return {
        "event_id": event_id,
        "log_event_id": log_event_id,
        "event_type": message.get("body"),
        "event_name": attributes.get("event.name"),
        "event_timestamp_utc": parse_utc_timestamp(attributes.get("event.timestamp")),
        "session_id": attributes.get("session.id"),
        "organization_id": attributes.get("organization.id"),
        "user_email": attributes.get("user.email") or resource.get("user.email"),
        "user_id": attributes.get("user.id"),
        "user_account_uuid": attributes.get("user.account_uuid"),
        "terminal_type": attributes.get("terminal.type"),
        "scope_name": scope.get("name"),
        "scope_version": scope.get("version"),
        "host_arch": resource.get("host.arch"),
        "host_name": resource.get("host.name"),
        "os_type": resource.get("os.type"),
        "os_version": resource.get("os.version"),
        "service_name": resource.get("service.name"),
        "service_version": resource.get("service.version"),
        "user_profile": resource.get("user.profile"),
        "user_serial": resource.get("user.serial"),
        "attributes_json": as_json(attributes),
        "resource_json": as_json(resource),
    }


def normalize_event_specific(event_id: str, message: JsonObject) -> tuple[str, JsonObject] | None:
    attributes = clean_mapping(message.get("attributes"))
    body = message.get("body")

    if body == "claude_code.api_request":
        return "api_requests", {
            "event_id": event_id,
            "model": attributes.get("model"),
            "cost_usd": parse_float(attributes.get("cost_usd")),
            "duration_ms": parse_int(attributes.get("duration_ms")),
            "input_tokens": parse_int(attributes.get("input_tokens")),
            "output_tokens": parse_int(attributes.get("output_tokens")),
            "cache_read_tokens": parse_int(attributes.get("cache_read_tokens")),
            "cache_creation_tokens": parse_int(attributes.get("cache_creation_tokens")),
        }

    if body == "claude_code.api_error":
        return "api_errors", {
            "event_id": event_id,
            "model": attributes.get("model"),
            "status_code": attributes.get("status_code"),
            "error_text": attributes.get("error"),
            "duration_ms": parse_int(attributes.get("duration_ms")),
            "attempt": parse_int(attributes.get("attempt")),
        }

    if body == "claude_code.tool_decision":
        return "tool_decisions", {
            "event_id": event_id,
            "tool_name": attributes.get("tool_name"),
            "decision": attributes.get("decision"),
            "source": attributes.get("source"),
        }

    if body == "claude_code.tool_result":
        return "tool_results", {
            "event_id": event_id,
            "tool_name": attributes.get("tool_name"),
            "decision_type": attributes.get("decision_type"),
            "decision_source": attributes.get("decision_source"),
            "success": parse_bool(attributes.get("success")),
            "duration_ms": parse_int(attributes.get("duration_ms")),
            "tool_result_size_bytes": parse_int(attributes.get("tool_result_size_bytes")),
        }

    if body == "claude_code.user_prompt":
        return "user_prompts", {
            "event_id": event_id,
            "prompt_redacted": attributes.get("prompt") == "<REDACTED>",
            "prompt_length": parse_int(attributes.get("prompt_length")),
        }

    return None
