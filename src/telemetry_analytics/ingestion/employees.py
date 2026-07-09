from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


EmployeeRow = dict[str, str]
JsonObject = dict[str, Any]

EMPLOYEE_COLUMNS = ["email", "full_name", "practice", "level", "location"]


def load_employees_csv(path: str | Path) -> list[EmployeeRow]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in EMPLOYEE_COLUMNS if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"employees CSV missing columns: {', '.join(missing)}")

        employees: list[EmployeeRow] = []
        for row_number, row in enumerate(reader, start=2):
            email = (row.get("email") or "").strip()
            if not email:
                raise ValueError(f"employees CSV row {row_number}: email is required")
            employees.append({column: (row.get(column) or "").strip() for column in EMPLOYEE_COLUMNS})

    return employees


def index_employees_by_email(employees: list[EmployeeRow]) -> dict[str, EmployeeRow]:
    return {employee["email"]: employee for employee in employees}


def enrich_event_rows(events: list[JsonObject], employees: list[EmployeeRow]) -> list[JsonObject]:
    employees_by_email = index_employees_by_email(employees)
    enriched: list[JsonObject] = []
    for event in events:
        employee = employees_by_email.get(str(event.get("user_email") or ""))
        enriched.append({**event, **{f"employee_{key}": value for key, value in (employee or {}).items()}})
    return enriched
