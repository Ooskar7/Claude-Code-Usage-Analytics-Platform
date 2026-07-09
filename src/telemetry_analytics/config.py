from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Settings:
    db_path: Path
    raw_dir: Path
    sample_dir: Path


def _path_from_env(name: str, default: str) -> Path:
    value = os.environ.get(name, default)
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def get_settings() -> Settings:
    return Settings(
        db_path=_path_from_env("TELEMETRY_DB_PATH", "data/warehouse/telemetry.duckdb"),
        raw_dir=_path_from_env("TELEMETRY_RAW_DIR", "data/raw"),
        sample_dir=_path_from_env("TELEMETRY_SAMPLE_DIR", "data/sample"),
    )
