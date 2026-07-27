from __future__ import annotations

from collections import Counter
from pathlib import Path

from ...utils.paths import repo_root
from ...utils.subproc import RunResult
from .baseline import _baseline_regressions, _load_hygiene_baseline, _path_budget_regressions
from .detectors import _collect_all_issues
from .reporting import _build_stdout, _write_reports

CATEGORY_THRESHOLDS = {
    "defensive_conversion": 50,
    "hasattr_coupling": 22,
    "any_type_hint": 0,
    "forbidden_getattr": 0,
    "forbidden_api": 0,
    "resource_leak": 0,
    "cleanup_hotspot": 96,
    "silent_broad_except": 4,
    "logged_broad_except": 0,
    "fallback_broad_except": 0,
}


def _resolved_category_thresholds(root: Path) -> dict[str, int]:
    thresholds = dict(CATEGORY_THRESHOLDS)
    baseline = _load_hygiene_baseline(root)

    for category in baseline.gated_categories:
        baseline_count = baseline.counts.get(category)
        if isinstance(baseline_count, int):
            thresholds[category] = baseline_count

    return thresholds


def code_hygiene_runner() -> RunResult:
    root = repo_root()
    baseline = _load_hygiene_baseline(root)
    category_thresholds = _resolved_category_thresholds(root)
    issues = _collect_all_issues(root)

    active_counts: Counter[str] = Counter()
    suppressed_counts: Counter[str] = Counter()
    for issue in issues:
        if issue.suppressed:
            suppressed_counts[issue.category] += 1
        else:
            active_counts[issue.category] += 1

    stdout_lines = _build_stdout(issues, active_counts, suppressed_counts, category_thresholds=category_thresholds)
    _write_reports(root, issues, active_counts, suppressed_counts, category_thresholds=category_thresholds)

    count_regressions = _baseline_regressions(active_counts, baseline)
    active_issues = [issue for issue in issues if not issue.suppressed]
    path_regressions = _path_budget_regressions(active_issues, baseline)
    if path_regressions:
        stdout_lines.append("")
        stdout_lines.append("Path-budget regressions:")
        stdout_lines.extend(
            f"  {category} {path}: current={current} baseline={expected}"
            for category, path, current, expected in path_regressions
        )

    should_fail = bool(count_regressions or path_regressions) or any(
        active_counts.get(category, 0) > threshold for category, threshold in category_thresholds.items()
    )

    return RunResult(
        command_str="(internal) code hygiene check",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=1 if should_fail else 0,
    )
