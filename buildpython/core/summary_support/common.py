from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def coverage_status(coverage: dict[str, Any]) -> str | None:
    summary = coverage.get("summary", {})
    if not isinstance(summary, dict):
        return None
    status = summary.get("status")
    return status if isinstance(status, str) else None


def file_size_counts(payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], int, int]:
    counts = payload.get("counts", {})
    if not isinstance(counts, dict):
        return {}, {}, 0, 0
    file_counts = counts.get("file_lines", counts)
    import_counts = counts.get("import_block_lines", {})
    flat_directories = counts.get("flat_directories", 0)
    delegation_candidates = counts.get("delegation_candidates", 0)
    return (
        file_counts if isinstance(file_counts, dict) else {},
        import_counts if isinstance(import_counts, dict) else {},
        flat_directories if isinstance(flat_directories, int) else 0,
        delegation_candidates if isinstance(delegation_candidates, int) else 0,
    )


def coerce_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default
