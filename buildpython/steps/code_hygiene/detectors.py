from __future__ import annotations

from pathlib import Path

from .ast_scanners import (
    _detect_broad_exception_patterns,
    _detect_forbidden_api_usage,
    _detect_resource_leaks,
)
from .baseline import (
    _baseline_delta,
    _baseline_regressions,
    _iter_python_files,
    _load_hygiene_baseline,
    _path_budget_regressions,
)
from .models import HygieneBaseline, HygieneIssue
from .runtime_scanners import _detect_runtime_copy_hotspots
from .text_scanners import (
    _detect_any_type_hints,
    _detect_cleanup_hotspots,
    _detect_defensive_conversions,
    _detect_forbidden_getattr,
    _detect_hasattr_coupling,
    _detect_test_naming_issues,
)


def _collect_all_issues(root: Path) -> list[HygieneIssue]:
    all_issues: list[HygieneIssue] = []

    for path in _iter_python_files(root):
        all_issues.extend(_detect_defensive_conversions(path, root))
        all_issues.extend(_detect_hasattr_coupling(path, root))
        all_issues.extend(_detect_any_type_hints(path, root))
        all_issues.extend(_detect_runtime_copy_hotspots(path, root))
        all_issues.extend(_detect_forbidden_getattr(path, root))
        all_issues.extend(_detect_forbidden_api_usage(path, root))
        all_issues.extend(_detect_resource_leaks(path, root))
        all_issues.extend(_detect_cleanup_hotspots(path, root))
        all_issues.extend(_detect_broad_exception_patterns(path, root))

    all_issues.extend(_detect_test_naming_issues(root))

    return all_issues
