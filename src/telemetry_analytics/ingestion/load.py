from __future__ import annotations

from pathlib import Path

from telemetry_analytics.ingestion.employees import load_employees_csv
from telemetry_analytics.ingestion.parser import (
    ParseError,
    ParsedBatch,
    iter_jsonl_batches,
    iter_log_events,
)
from telemetry_analytics.normalize.telemetry import (
    NormalizationError,
    NormalizedTelemetry,
    add_parse_error_log_event,
    normalize_parsed_batch,
    normalize_parsed_log_event,
)


def load_telemetry_jsonl(path: str | Path) -> NormalizedTelemetry:
    source_file = str(path)
    normalized = NormalizedTelemetry()

    for batch_item in iter_jsonl_batches(path):
        if isinstance(batch_item, ParseError):
            normalized.parse_errors.append(batch_item)
            continue

        normalized.raw_log_batches.append(normalize_parsed_batch(source_file, batch_item))
        _load_batch_events(source_file, batch_item, normalized)

    return normalized


def load_telemetry_dataset(
    telemetry_path: str | Path,
    employees_path: str | Path,
) -> NormalizedTelemetry:
    normalized = load_telemetry_jsonl(telemetry_path)
    normalized.employees.extend(load_employees_csv(employees_path))
    return normalized


def _load_batch_events(
    source_file: str,
    parsed_batch: ParsedBatch,
    normalized: NormalizedTelemetry,
) -> None:
    for event_item in iter_log_events(parsed_batch):
        if isinstance(event_item, ParseError):
            normalized.parse_errors.append(event_item)
            add_parse_error_log_event(source_file, parsed_batch, event_item, normalized)
            continue

        try:
            normalize_parsed_log_event(source_file, parsed_batch, event_item, normalized)
        except (TypeError, ValueError) as exc:
            normalized.normalization_errors.append(
                NormalizationError(
                    source=source_file,
                    line_number=parsed_batch.line_number,
                    event_index=event_item.event_index,
                    message=str(exc),
                    raw_message=event_item.message,
                )
            )
