from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import _DEBT_BASELINE_PATH
from .models import CoverageBaseline, CoverageRegression


def _coerce_float(value: object, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    return default


def _coerce_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return default


def _lowest_covered_sort_key(item: dict[str, Any]) -> tuple[float, int, str]:
    return (
        _coerce_float(item.get("percent", 0.0)),
        -_coerce_int(item.get("num_statements", 0)),
        str(item.get("path", "")),
    )


def build_coverage_report(payload: dict[str, Any], baseline: CoverageBaseline) -> dict[str, Any]:
    files = _normalize_files(payload)
    totals = _extract_totals(payload)
    total_percent = _percent_from_counts(
        covered=int(totals.get("covered_lines", 0)),
        statements=int(totals.get("num_statements", 0)),
    )

    tracked_prefixes: list[dict[str, Any]] = []
    regressions: list[CoverageRegression] = []
    for prefix, expected in baseline.tracked_prefixes.items():
        aggregate = _aggregate_prefix(files, prefix)
        current_percent = _percent_from_counts(
            covered=int(aggregate.get("covered_lines", 0)),
            statements=int(aggregate.get("num_statements", 0)),
        )
        if current_percent < float(expected):
            regressions.append(
                CoverageRegression(
                    kind="prefix",
                    target=prefix,
                    current=current_percent,
                    baseline=float(expected),
                )
            )
        tracked_prefixes.append(
            {
                "prefix": prefix,
                "percent": round(current_percent, 2),
                "baseline": round(float(expected), 2),
                "delta": round(current_percent - float(expected), 2),
                "covered_lines": int(aggregate.get("covered_lines", 0)),
                "num_statements": int(aggregate.get("num_statements", 0)),
                "status": "fail" if current_percent < float(expected) else "ok",
            }
        )

    minimum_total = baseline.minimum_total_percent
    if minimum_total is not None and total_percent < float(minimum_total):
        regressions.append(
            CoverageRegression(
                kind="total",
                target="total",
                current=total_percent,
                baseline=float(minimum_total),
            )
        )

    watch_file_rows: list[dict[str, Any]] = []
    for rel_path in baseline.watch_files:
        file_summary = files.get(rel_path)
        if file_summary is None:
            watch_file_rows.append(
                {
                    "path": rel_path,
                    "percent": None,
                    "covered_lines": 0,
                    "num_statements": 0,
                    "status": "missing",
                }
            )
            continue
        watch_file_rows.append(
            {
                "path": rel_path,
                "percent": round(float(file_summary.get("percent", 0.0)), 2),
                "covered_lines": int(file_summary.get("covered_lines", 0)),
                "num_statements": int(file_summary.get("num_statements", 0)),
                "status": "ok",
            }
        )

    lowest_covered_rows: list[dict[str, Any]] = []
    for rel_path, item in files.items():
        num_statements = _coerce_int(item.get("num_statements", 0))
        if num_statements <= 0:
            continue
        lowest_covered_rows.append(
            {
                "path": rel_path,
                "percent": round(_coerce_float(item.get("percent", 0.0)), 2),
                "covered_lines": _coerce_int(item.get("covered_lines", 0)),
                "num_statements": num_statements,
            }
        )

    lowest_covered = sorted(lowest_covered_rows, key=_lowest_covered_sort_key)[:20]

    return {
        "summary": {
            "total_percent": round(total_percent, 2),
            "covered_lines": int(totals.get("covered_lines", 0)),
            "num_statements": int(totals.get("num_statements", 0)),
            "files": len(files),
        },
        "baseline": {
            "minimum_total_percent": None if minimum_total is None else round(float(minimum_total), 2),
            "delta_total_percent": None if minimum_total is None else round(total_percent - float(minimum_total), 2),
            "tracked_prefixes": {prefix: round(float(value), 2) for prefix, value in baseline.tracked_prefixes.items()},
            "regressions": [
                {
                    "kind": item.kind,
                    "target": item.target,
                    "current": round(item.current, 2),
                    "baseline": round(item.baseline, 2),
                }
                for item in regressions
            ],
        },
        "tracked_prefixes": tracked_prefixes,
        "watch_files": watch_file_rows,
        "lowest_covered_files": lowest_covered,
    }


def _load_coverage_baseline(root: Path) -> CoverageBaseline:
    config_path = root / _DEBT_BASELINE_PATH
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return CoverageBaseline(minimum_total_percent=None, tracked_prefixes={}, watch_files=())

    section = payload.get("coverage", {})
    minimum_total_raw = section.get("minimum_total_percent")
    minimum_total = None
    if isinstance(minimum_total_raw, int | float):
        minimum_total = float(minimum_total_raw)

    tracked_prefixes_raw = section.get("tracked_prefixes", {})
    tracked_prefixes = {
        str(prefix): float(value)
        for prefix, value in tracked_prefixes_raw.items()
        if isinstance(prefix, str) and isinstance(value, int | float)
    }

    watch_files = tuple(str(path) for path in section.get("watch_files", []) if isinstance(path, str))
    return CoverageBaseline(
        minimum_total_percent=minimum_total,
        tracked_prefixes=tracked_prefixes,
        watch_files=watch_files,
    )


def _load_json_file(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _normalize_files(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw_files = payload.get("files", {})
    if not isinstance(raw_files, dict):
        return {}

    files: dict[str, dict[str, Any]] = {}
    for rel_path, file_payload in raw_files.items():
        if not isinstance(rel_path, str) or not isinstance(file_payload, dict):
            continue
        summary = file_payload.get("summary", {})
        if not isinstance(summary, dict):
            continue
        covered = int(summary.get("covered_lines", 0) or 0)
        statements = int(summary.get("num_statements", 0) or 0)
        files[rel_path] = {
            "covered_lines": covered,
            "num_statements": statements,
            "percent": _percent_from_counts(covered=covered, statements=statements),
        }
    return files


def _extract_totals(payload: dict[str, Any]) -> dict[str, int]:
    totals = payload.get("totals", {})
    if not isinstance(totals, dict):
        return {"covered_lines": 0, "num_statements": 0}
    return {
        "covered_lines": int(totals.get("covered_lines", 0) or 0),
        "num_statements": int(totals.get("num_statements", 0) or 0),
    }


def _aggregate_prefix(files: dict[str, dict[str, Any]], prefix: str) -> dict[str, int]:
    covered = 0
    statements = 0
    for rel_path, summary in files.items():
        if rel_path.startswith(prefix):
            covered += int(summary.get("covered_lines", 0))
            statements += int(summary.get("num_statements", 0))
    return {"covered_lines": covered, "num_statements": statements}


def _percent_from_counts(*, covered: int, statements: int) -> float:
    if statements <= 0:
        return 0.0
    return round((covered / statements) * 100.0, 2)
