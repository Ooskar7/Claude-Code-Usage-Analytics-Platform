from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from telemetry_analytics.ingestion.parser import (
    ParseError,
    ParsedBatch,
    ParsedLogEvent,
    batch_partition_date,
)
from telemetry_analytics.normalize.records import as_json, normalize_common_event, normalize_event_specific


JsonObject = dict[str, Any]


class TelemetryValidationError(ValueError):
    """Raised when a parsed telemetry event is missing required common fields."""


@dataclass(frozen=True)
class NormalizationError:
    source: str
    line_number: int | None
    event_index: int | None
    message: str
    raw_message: JsonObject | None = None


@dataclass(frozen=True)
class ValidationError:
    source: str
    line_number: int | None
    event_index: int | None
    message: str
    raw_message: JsonObject | None = None


@dataclass
class NormalizedTelemetry:
    raw_log_batches: list[JsonObject] = field(default_factory=list)
    raw_log_events: list[JsonObject] = field(default_factory=list)
    events: list[JsonObject] = field(default_factory=list)
    api_requests: list[JsonObject] = field(default_factory=list)
    api_errors: list[JsonObject] = field(default_factory=list)
    tool_decisions: list[JsonObject] = field(default_factory=list)
    tool_results: list[JsonObject] = field(default_factory=list)
    user_prompts: list[JsonObject] = field(default_factory=list)
    employees: list[JsonObject] = field(default_factory=list)
    parse_errors: list[ParseError] = field(default_factory=list)
    validation_errors: list[ValidationError] = field(default_factory=list)
    normalization_errors: list[NormalizationError] = field(default_factory=list)

    def add_event_specific(self, table_name: str, row: JsonObject) -> None:
        getattr(self, table_name).append(row)


def stable_id(*parts: object) -> str:
    payload = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def batch_id_for(source_file: str, parsed_batch: ParsedBatch) -> str:
    return stable_id(source_file, parsed_batch.line_number, as_json(parsed_batch.batch))


def log_event_id_for(
    source_file: str,
    parsed_batch: ParsedBatch,
    event_index: int,
    log_event: JsonObject | None,
) -> str:
    if isinstance(log_event, dict):
        log_event_id = log_event.get("id")
        if isinstance(log_event_id, str) and log_event_id:
            return log_event_id
    return stable_id(source_file, parsed_batch.line_number, event_index, as_json(log_event or {}))


def normalize_parsed_batch(source_file: str, parsed_batch: ParsedBatch) -> JsonObject:
    batch = parsed_batch.batch
    return {
        "batch_id": batch_id_for(source_file, parsed_batch),
        "source_file": source_file,
        "line_number": parsed_batch.line_number,
        "message_type": batch.get("messageType"),
        "owner": batch.get("owner"),
        "log_group": batch.get("logGroup"),
        "log_stream": batch.get("logStream"),
        "subscription_filters": as_json(batch.get("subscriptionFilters") or []),
        "partition_year": batch.get("year"),
        "partition_month": batch.get("month"),
        "partition_day": batch.get("day"),
        "raw_json": as_json(batch),
    }


def normalize_raw_log_event(
    source_file: str,
    parsed_batch: ParsedBatch,
    event_index: int,
    log_event: JsonObject,
    message: JsonObject | None,
    *,
    parse_status: str,
    parse_error: str | None = None,
) -> JsonObject:
    batch_id = batch_id_for(source_file, parsed_batch)
    return {
        "log_event_id": log_event_id_for(source_file, parsed_batch, event_index, log_event),
        "batch_id": batch_id,
        "event_index": event_index,
        "ingestion_timestamp_ms": log_event.get("timestamp"),
        "batch_date": batch_partition_date(parsed_batch.batch),
        "raw_message_json": as_json(message) if message is not None else None,
        "raw_log_event_json": as_json(log_event),
        "parse_status": parse_status,
        "parse_error": parse_error,
    }


def normalize_parsed_log_event(
    source_file: str,
    parsed_batch: ParsedBatch,
    parsed_event: ParsedLogEvent,
    normalized: NormalizedTelemetry,
) -> None:
    validate_common_message(parsed_event.message)
    raw_log_event = normalize_raw_log_event(
        source_file,
        parsed_batch,
        parsed_event.event_index,
        parsed_event.log_event,
        parsed_event.message,
        parse_status="parsed",
    )

    event_id = raw_log_event["log_event_id"]
    event_row = normalize_common_event(event_id, raw_log_event["log_event_id"], parsed_event.message)

    specific = normalize_event_specific(event_id, parsed_event.message)
    normalized.raw_log_events.append(raw_log_event)
    normalized.events.append(event_row)
    if specific is not None:
        table_name, row = specific
        normalized.add_event_specific(table_name, row)


def validate_common_message(message: JsonObject) -> None:
    if not isinstance(message.get("body"), str) or not message.get("body"):
        raise TelemetryValidationError("missing required common field: body")

    attributes = message.get("attributes")
    if not isinstance(attributes, dict):
        raise TelemetryValidationError("missing required common field: attributes")

    required_attributes = [
        "event.timestamp",
        "event.name",
        "organization.id",
        "session.id",
        "user.email",
        "user.id",
    ]
    missing = [field_name for field_name in required_attributes if not attributes.get(field_name)]
    if missing:
        raise TelemetryValidationError(f"missing required common field(s): {', '.join(missing)}")


def add_parse_error_log_event(
    source_file: str,
    parsed_batch: ParsedBatch,
    parse_error: ParseError,
    normalized: NormalizedTelemetry,
) -> None:
    if not isinstance(parse_error.raw_value, dict) or parse_error.event_index is None:
        return

    normalized.raw_log_events.append(
        normalize_raw_log_event(
            source_file,
            parsed_batch,
            parse_error.event_index,
            parse_error.raw_value,
            None,
            parse_status="parse_error",
            parse_error=parse_error.message,
        )
    )


def add_validation_error_log_event(
    source_file: str,
    parsed_batch: ParsedBatch,
    parsed_event: ParsedLogEvent,
    error_message: str,
    normalized: NormalizedTelemetry,
) -> None:
    normalized.raw_log_events.append(
        normalize_raw_log_event(
            source_file,
            parsed_batch,
            parsed_event.event_index,
            parsed_event.log_event,
            parsed_event.message,
            parse_status="validation_error",
            parse_error=error_message,
        )
    )


def add_normalization_error_log_event(
    source_file: str,
    parsed_batch: ParsedBatch,
    parsed_event: ParsedLogEvent,
    error_message: str,
    normalized: NormalizedTelemetry,
) -> None:
    normalized.raw_log_events.append(
        normalize_raw_log_event(
            source_file,
            parsed_batch,
            parsed_event.event_index,
            parsed_event.log_event,
            parsed_event.message,
            parse_status="normalization_error",
            parse_error=error_message,
        )
    )
