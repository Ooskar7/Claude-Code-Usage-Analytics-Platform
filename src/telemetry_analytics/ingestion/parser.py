from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Iterable


JsonObject = dict[str, Any]


@dataclass(frozen=True)
class ParsedBatch:
    line_number: int
    batch: JsonObject


@dataclass(frozen=True)
class ParsedLogEvent:
    batch_line_number: int
    event_index: int
    log_event: JsonObject
    message: JsonObject


@dataclass(frozen=True)
class ParseError:
    source: str
    line_number: int | None
    event_index: int | None
    message: str
    raw_value: str | JsonObject | None = None


def parse_batch_line(line: str, line_number: int) -> ParsedBatch:
    try:
        batch = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ValueError(f"line {line_number}: invalid JSONL batch: {exc.msg}") from exc

    if not isinstance(batch, dict):
        raise ValueError(f"line {line_number}: batch must be a JSON object")

    log_events = batch.get("logEvents")
    if log_events is None:
        raise ValueError(f"line {line_number}: missing logEvents")
    if not isinstance(log_events, list):
        raise ValueError(f"line {line_number}: logEvents must be a list")

    return ParsedBatch(line_number=line_number, batch=batch)


def iter_jsonl_batches(path: str | Path) -> Iterable[ParsedBatch | ParseError]:
    source = str(path)
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                yield parse_batch_line(stripped, line_number)
            except ValueError as exc:
                yield ParseError(source=source, line_number=line_number, event_index=None, message=str(exc), raw_value=stripped)


def parse_nested_message(log_event: JsonObject, line_number: int, event_index: int) -> JsonObject:
    raw_message = log_event.get("message")
    if not isinstance(raw_message, str):
        raise ValueError(f"line {line_number} event {event_index}: message must be a JSON string")

    try:
        message = json.loads(raw_message)
    except json.JSONDecodeError as exc:
        raise ValueError(f"line {line_number} event {event_index}: invalid nested message: {exc.msg}") from exc

    if not isinstance(message, dict):
        raise ValueError(f"line {line_number} event {event_index}: nested message must be a JSON object")

    return message


def iter_log_events(parsed_batch: ParsedBatch) -> Iterable[ParsedLogEvent | ParseError]:
    for event_index, log_event in enumerate(parsed_batch.batch["logEvents"]):
        if not isinstance(log_event, dict):
            yield ParseError(
                source="logEvents",
                line_number=parsed_batch.line_number,
                event_index=event_index,
                message="log event must be a JSON object",
                raw_value=None,
            )
            continue

        try:
            message = parse_nested_message(log_event, parsed_batch.line_number, event_index)
        except ValueError as exc:
            yield ParseError(
                source="message",
                line_number=parsed_batch.line_number,
                event_index=event_index,
                message=str(exc),
                raw_value=log_event,
            )
            continue

        yield ParsedLogEvent(
            batch_line_number=parsed_batch.line_number,
            event_index=event_index,
            log_event=log_event,
            message=message,
        )


def batch_partition_date(batch: JsonObject) -> date | None:
    try:
        year = int(batch["year"])
        month = int(batch["month"])
        day = int(batch["day"])
    except (KeyError, TypeError, ValueError):
        return None
    return date(year, month, day)
