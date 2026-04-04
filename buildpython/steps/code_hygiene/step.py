from __future__ import annotations

from collections import Counter

from ...utils.paths import repo_root
from ...utils.subproc import RunResult
from .detectors import (
    HygieneIssue,
    _collect_all_issues,
    _detect_broad_exception_patterns,
    _detect_cleanup_hotspots,
    _detect_runtime_copy_hotspots,
)
from .reporting import _build_stdout, _write_reports


CATEGORY_THRESHOLDS = {
    "defensive_conversion": 50,
    "hasattr_coupling": 22,
    "any_type_hint": 127,
    "forbidden_getattr": 94,
    "forbidden_api": 0,
    "resource_leak": 0,
    "cleanup_hotspot": 96,
    "silent_broad_except": 4,
    "logged_broad_except": 0,
    "fallback_broad_except": 0,
}


def code_hygiene_runner() -> RunResult:
    root = repo_root()
    issues = _collect_all_issues(root)

    active_counts: Counter[str] = Counter()
    suppressed_counts: Counter[str] = Counter()
    for issue in issues:
        if issue.suppressed:
            suppressed_counts[issue.category] += 1
        else:
            active_counts[issue.category] += 1

    stdout_lines = _build_stdout(issues, active_counts, suppressed_counts, category_thresholds=CATEGORY_THRESHOLDS)
    _write_reports(root, issues, active_counts, suppressed_counts, category_thresholds=CATEGORY_THRESHOLDS)

    should_fail = any(active_counts.get(category, 0) > threshold for category, threshold in CATEGORY_THRESHOLDS.items())

    return RunResult(
        command_str="(internal) code hygiene check",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=1 if should_fail else 0,
    )
