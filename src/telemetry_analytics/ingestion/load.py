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
    TelemetryValidationError,
    ValidationError,
    add_normalization_error_log_event,
    add_parse_error_log_event,
    add_validation_error_log_event,
    normalize_parsed_batch,
    normalize_parsed_log_event,
)


def load_telemetry_jsonl(path: str | Path) -> NormalizedTelemetry:
    source_file = str(path)
    normalized = NormalizedTelemetry()
    telemetry_path = Path(path)

    if not telemetry_path.exists():
        normalized.validation_errors.append(
            ValidationError(
                source=source_file,
                line_number=None,
                event_index=None,
                message=f"missing input file: {telemetry_path}",
            )
        )
        return normalized

    for batch_item in iter_jsonl_batches(telemetry_path):
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
    employees_file = Path(employees_path)
    if not employees_file.exists():
        normalized.validation_errors.append(
            ValidationError(
                source=str(employees_file),
                line_number=None,
                event_index=None,
                message=f"missing input file: {employees_file}",
            )
        )
        return normalized

    try:
        employees = load_employees_csv(employees_file)
    except ValueError as exc:
        normalized.validation_errors.append(
            ValidationError(
                source=str(employees_file),
                line_number=None,
                event_index=None,
                message=str(exc),
            )
        )
        employees = []

    normalized.employees.extend(employees)
    validate_employee_enrichment(normalized)
    return normalized


def validate_employee_enrichment(normalized: NormalizedTelemetry) -> None:
    employee_emails = {employee["email"] for employee in normalized.employees}
    event_emails = {str(event.get("user_email") or "") for event in normalized.events}
    missing_employees = sorted(email for email in event_emails if email and email not in employee_emails)

    for email in missing_employees:
        normalized.validation_errors.append(
            ValidationError(
                source="employees",
                line_number=None,
                event_index=None,
                message=f"employee enrichment mismatch: no employees.csv row for {email}",
            )
        )


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
        except TelemetryValidationError as exc:
            normalized.validation_errors.append(
                ValidationError(
                    source=source_file,
                    line_number=parsed_batch.line_number,
                    event_index=event_item.event_index,
                    message=str(exc),
                    raw_message=event_item.message,
                )
            )
            add_validation_error_log_event(
                source_file,
                parsed_batch,
                event_item,
                str(exc),
                normalized,
            )
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
            add_normalization_error_log_event(
                source_file,
                parsed_batch,
                event_item,
                str(exc),
                normalized,
            )
