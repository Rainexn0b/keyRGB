from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

from ..model import StepHealth
from ..summary_support.common import read_json_if_exists


class _HealthScorer(Protocol):
    def __call__(self, payload: Mapping[str, Any]) -> StepHealth | None: ...


def _clamp_score(value: float) -> float:
    return max(0, min(100, value))


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, dict) else {}


def _count(mapping: Mapping[str, Any], key: str) -> int:
    value = mapping.get(key, 0)
    return int(value) if isinstance(value, int | float) else 0


def _valid_counts(value: object) -> bool:
    if isinstance(value, dict):
        return bool(value) and all(_valid_counts(count) for count in value.values())
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _marker_health(payload: Mapping[str, Any]) -> StepHealth:
    counts = _mapping(payload.get("marker_counts"))
    gated = _mapping(payload.get("baseline")).get("gated_markers", [])
    gated_markers = gated if isinstance(gated, list) else []
    debt = sum(_count(counts, str(marker)) for marker in gated_markers)
    return StepHealth("Marker Health", _clamp_score(100 - debt * 20))


def _file_size_health(payload: Mapping[str, Any]) -> StepHealth:
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
    return StepHealth("File Size Health", _clamp_score(100 - penalty))


def _loc_health(payload: Mapping[str, Any]) -> StepHealth:
    counts = _mapping(payload.get("counts"))
    monitor_penalty = _count(counts, "monitor") * 0.25
    penalty = (
        monitor_penalty
        + _count(counts, "refactor") * 5
        + _count(counts, "critical") * 12
        + _count(counts, "severe") * 25
    )
    return StepHealth("LOC Health", _clamp_score(100 - penalty))


def _hygiene_health(payload: Mapping[str, Any]) -> StepHealth:
    active = _mapping(payload.get("active_counts"))
    high_weight = {"forbidden_api", "resource_leak", "silent_broad_except", "any_type_hint"}
    medium_weight = {"forbidden_getattr", "hasattr_coupling", "runtime_copy_hotspot", "test_naming"}
    penalty = 0
    for category, value in active.items():
        if not isinstance(value, int | float):
            continue
        weight = 20 if category in high_weight else 8 if category in medium_weight else 4
        penalty += int(value) * weight
    return StepHealth("Hygiene Health", _clamp_score(100 - penalty))


def _architecture_health(payload: Mapping[str, Any]) -> StepHealth:
    summary = _mapping(payload.get("summary"))
    penalty = _count(summary, "errors") * 25 + _count(summary, "warnings") * 5
    return StepHealth("Architecture Health", _clamp_score(100 - penalty))


def _transparency_health(payload: Mapping[str, Any]) -> StepHealth:
    counts = _mapping(payload.get("counts"))
    penalty = (
        _count(counts, "naked_except") * 30
        + _count(counts, "baseexception_catch") * 30
        + _count(counts, "broad_except_unlogged") * 20
        + _count(counts, "broad_except_logged_no_traceback") * 8
        + _count(counts, "broad_except_traceback_logged") * 5
    )
    return StepHealth("Exception Health", _clamp_score(100 - penalty))


def _dead_code_health(payload: Mapping[str, Any]) -> StepHealth:
    penalty = _count(payload, "actionable_count") * 20
    return StepHealth("Dead Code Health", _clamp_score(100 - penalty))


# The summaries count diagnostics once; parsing individual source excerpts can double count them.
def _diagnostic_health(step_name: str, output: str, *, failed: bool) -> StepHealth | None:
    if step_name == "Ruff":
        match = re.search(r"^Found (\d+) errors?\.$", output, re.MULTILINE)
        if match:
            return StepHealth("Ruff Health", _clamp_score(100 - int(match[1]) * 5))
        if not failed and "All checks passed!" in output:
            return StepHealth("Ruff Health", 100)
    elif step_name == "Type Check":
        match = re.search(r"^Found (\d+) errors? in ", output, re.MULTILINE)
        if match:
            return StepHealth("Type Check Health", _clamp_score(100 - int(match[1]) * 10))
        if not failed and re.search(r"^Success: no issues found in \d+ source files?", output, re.MULTILINE):
            return StepHealth("Type Check Health", 100)
    return None


def build_step_health(
    step_name: str,
    *,
    stdout: str,
    stderr: str,
    report_dir: Path,
    failed: bool,
    report_names: tuple[str, ...] = (),
) -> StepHealth | None:
    """Penalty scores for current findings, independent of gate status and coverage."""
    if step_name in {"Ruff", "Type Check"}:
        return _diagnostic_health(step_name, f"{stdout}\n{stderr}", failed=failed)

    report_specs: dict[str, tuple[str, str, _HealthScorer]] = {
        "Code Markers": ("code-markers.json", "marker_counts", _marker_health),
        "File Size": ("file-size-analysis.json", "counts", _file_size_health),
        "LOC Check": ("loc-check.json", "counts", _loc_health),
        "Code Hygiene": ("code-hygiene.json", "active_counts", _hygiene_health),
        "Architecture Validation": ("architecture-validation.json", "summary", _architecture_health),
        "Exception Transparency": ("exception-transparency.json", "counts", _transparency_health),
        "Dead Code": ("dead-code-vulture.json", "actionable_count", _dead_code_health),
    }
    spec = report_specs.get(step_name)
    if spec is None:
        return None
    report_name, count_key, scorer = spec
    payload = read_json_if_exists(report_dir / report_name, report_names=report_names)
    if payload is None or count_key not in payload:
        return None
    counts = payload[count_key]
    if not _valid_counts(counts):
        return None
    if count_key != "actionable_count" and not isinstance(counts, dict):
        return None
    if step_name == "Architecture Validation" and not {"errors", "warnings"} <= _mapping(counts).keys():
        return None
    if step_name == "Code Markers" and not isinstance(_mapping(payload.get("baseline")).get("gated_markers"), list):
        return None
    return scorer(payload)
