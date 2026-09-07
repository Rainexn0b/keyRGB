from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from ..model import StepHealth
from ..summary_support.common import read_json_if_exists

_PYTEST_RESULT_PATTERN = re.compile(r"(\d+)\s+(passed|failed|errors?)\b")


class _HealthScorer(Protocol):
    def __call__(self, payload: Mapping[str, Any], *, failed: bool) -> StepHealth | None: ...


def _clamp_score(value: float) -> int:
    return max(0, min(100, round(value)))


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _count(mapping: Mapping[str, Any], key: str) -> int:
    value = mapping.get(key, 0)
    return int(value) if isinstance(value, int | float) else 0


def _failed_cap(score: int, *, failed: bool) -> int:
    return min(score, 49) if failed else score


def _pytest_health(stdout: str, stderr: str, *, failed: bool) -> StepHealth | None:
    result_lines = [line for line in f"{stdout}\n{stderr}".splitlines() if " in " in line]
    if not result_lines:
        return None
    counts: dict[str, int] = {}
    for count, category in _PYTEST_RESULT_PATTERN.findall(result_lines[-1]):
        normalized = "error" if category.startswith("error") else category
        counts[normalized] = counts.get(normalized, 0) + int(count)
    total = counts.get("passed", 0) + counts.get("failed", 0) + counts.get("error", 0)
    if total <= 0:
        return None
    score = _clamp_score(100 * counts.get("passed", 0) / total)
    return StepHealth("Test Health", _failed_cap(score, failed=failed))


def _marker_health(payload: Mapping[str, Any], *, failed: bool) -> StepHealth:
    counts = _mapping(payload.get("marker_counts"))
    gated = _mapping(payload.get("baseline")).get("gated_markers", [])
    gated_markers = gated if isinstance(gated, list) else []
    debt = sum(_count(counts, str(marker)) for marker in gated_markers)
    return StepHealth("Marker Health", _failed_cap(_clamp_score(100 - debt * 20), failed=failed))


def _file_size_health(payload: Mapping[str, Any], *, failed: bool) -> StepHealth:
    counts = _mapping(payload.get("counts"))
    files = _mapping(counts.get("file_lines"))
    imports = _mapping(counts.get("import_block_lines"))
    penalty = (
        _count(files, "refactor") * 3
        + _count(files, "critical") * 10
        + _count(files, "severe") * 20
        + _count(files, "extreme") * 30
        + _count(imports, "warning") * 0.5
        + _count(imports, "critical") * 4
        + _count(imports, "severe") * 10
        + _count(counts, "flat_directories") * 2
        + _count(counts, "delegation_candidates") * 5
        + _count(counts, "middleman_modules") * 2
        + _count(counts, "unreferenced_files") * 8
    )
    return StepHealth("File Size Health", _failed_cap(_clamp_score(100 - penalty), failed=failed))


def _loc_health(payload: Mapping[str, Any], *, failed: bool) -> StepHealth:
    counts = _mapping(payload.get("counts"))
    monitor_penalty = min(10.0, _count(counts, "monitor") * 0.25)
    penalty = (
        monitor_penalty
        + _count(counts, "refactor") * 5
        + _count(counts, "critical") * 12
        + _count(counts, "severe") * 25
    )
    return StepHealth("LOC Health", _failed_cap(_clamp_score(100 - penalty), failed=failed))


def _hygiene_health(payload: Mapping[str, Any], *, failed: bool) -> StepHealth:
    active = _mapping(payload.get("active_counts"))
    high_weight = {"forbidden_api", "resource_leak", "silent_broad_except", "any_type_hint"}
    medium_weight = {"forbidden_getattr", "hasattr_coupling", "runtime_copy_hotspot", "test_naming"}
    penalty = 0
    for category, value in active.items():
        if not isinstance(value, int | float):
            continue
        weight = 20 if category in high_weight else 8 if category in medium_weight else 4
        penalty += int(value) * weight
    return StepHealth("Hygiene Health", _failed_cap(_clamp_score(100 - penalty), failed=failed))


def _architecture_health(payload: Mapping[str, Any], *, failed: bool) -> StepHealth:
    summary = _mapping(payload.get("summary"))
    penalty = _count(summary, "errors") * 25 + _count(summary, "warnings") * 5
    return StepHealth("Architecture Health", _failed_cap(_clamp_score(100 - penalty), failed=failed))


def _coverage_health(payload: Mapping[str, Any], *, failed: bool) -> StepHealth | None:
    summary = _mapping(payload.get("summary"))
    total = summary.get("total_percent")
    if not isinstance(total, int | float):
        return None
    return StepHealth("Coverage", _failed_cap(_clamp_score(float(total)), failed=failed))


def _transparency_health(payload: Mapping[str, Any], *, failed: bool) -> StepHealth:
    counts = _mapping(payload.get("counts"))
    penalty = (
        _count(counts, "naked_except") * 30
        + _count(counts, "baseexception_catch") * 30
        + _count(counts, "broad_except_unlogged") * 20
        + _count(counts, "broad_except_logged_no_traceback") * 8
        + _count(counts, "broad_except_traceback_logged") * 5
    )
    return StepHealth("Exception Health", _failed_cap(_clamp_score(100 - penalty), failed=failed))


def _dead_code_health(payload: Mapping[str, Any], *, failed: bool) -> StepHealth:
    penalty = _count(payload, "actionable_count") * 20
    return StepHealth("Dead Code Health", _failed_cap(_clamp_score(100 - penalty), failed=failed))


def build_step_health(
    step_name: str,
    *,
    stdout: str,
    stderr: str,
    report_dir: Path,
    failed: bool,
    started_at: float | None = None,
) -> StepHealth | None:
    if step_name == "Pytest":
        return _pytest_health(stdout, stderr, failed=failed)

    report_specs: dict[str, tuple[str, _HealthScorer]] = {
        "Code Markers": ("code-markers.json", _marker_health),
        "File Size": ("file-size-analysis.json", _file_size_health),
        "LOC Check": ("loc-check.json", _loc_health),
        "Code Hygiene": ("code-hygiene.json", _hygiene_health),
        "Architecture Validation": ("architecture-validation.json", _architecture_health),
        "Coverage": ("coverage-summary.json", _coverage_health),
        "Exception Transparency": ("exception-transparency.json", _transparency_health),
        "Dead Code": ("dead-code-vulture.json", _dead_code_health),
    }
    spec = report_specs.get(step_name)
    if spec is None:
        return None
    report_name, scorer = spec
    report_path = report_dir / report_name
    if started_at is not None:
        try:
            if report_path.stat().st_mtime < started_at:
                return None
        except OSError:
            return None
    payload = read_json_if_exists(report_path)
    if payload is None:
        return None
    return scorer(payload, failed=failed)
