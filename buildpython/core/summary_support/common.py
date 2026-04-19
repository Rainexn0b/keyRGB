from __future__ import annotations

import json
from pathlib import Path
from typing import Any


_LOC_BUCKET_KEYS = (
    ("monitor", "monitor"),
    ("refactor", "refactor"),
    ("critical", "critical"),
    ("severe", "severe"),
)


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


def file_size_structure_candidate_counts(payload: dict[str, Any]) -> tuple[int, int]:
    counts = payload.get("counts", {})
    if not isinstance(counts, dict):
        return 0, 0
    middleman_modules = counts.get("middleman_modules", 0)
    unreferenced_files = counts.get("unreferenced_files", 0)
    return (
        middleman_modules if isinstance(middleman_modules, int) else 0,
        unreferenced_files if isinstance(unreferenced_files, int) else 0,
    )


def loc_check_counts(payload: dict[str, Any]) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    counts = _normalize_loc_counts(payload.get("counts", {}))
    counts_by_scope = payload.get("counts_by_scope", {})
    default_counts = _normalize_loc_counts(counts_by_scope.get("default", {}) if isinstance(counts_by_scope, dict) else {})
    test_counts = _normalize_loc_counts(counts_by_scope.get("tests", {}) if isinstance(counts_by_scope, dict) else {})

    count = payload.get("count")
    if isinstance(count, int):
        counts["total"] = count
    elif counts["total"] == 0:
        counts["total"] = default_counts["total"] + test_counts["total"]

    return counts, default_counts, test_counts


def loc_bucket_parts(counts: dict[str, Any], *, assignment: bool) -> list[str]:
    parts: list[str] = []
    for key, label in _LOC_BUCKET_KEYS:
        current = counts.get(key)
        if isinstance(current, int) and current:
            if assignment:
                parts.append(f"{label}={current}")
            else:
                parts.append(f"{label} {current}")
    return parts


def _normalize_loc_counts(raw_counts: object) -> dict[str, int]:
    counts = {key: 0 for key, _label in _LOC_BUCKET_KEYS}
    counts["total"] = 0
    if not isinstance(raw_counts, dict):
        return counts

    for key in (*[key for key, _label in _LOC_BUCKET_KEYS], "total"):
        value = raw_counts.get(key)
        if isinstance(value, int):
            counts[key] = value
    return counts


def coerce_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default
