from __future__ import annotations

from pathlib import Path

from . import ast_scanners as _ast_scanners
from . import baseline as _baseline
from . import models as _models
from . import runtime_scanners as _runtime_scanners
from . import text_scanners as _text_scanners

_baseline_delta = _baseline._baseline_delta
_baseline_regressions = _baseline._baseline_regressions
_iter_python_files = _baseline._iter_python_files
_load_hygiene_baseline = _baseline._load_hygiene_baseline
_path_budget_regressions = _baseline._path_budget_regressions

HygieneBaseline = _models.HygieneBaseline
HygieneIssue = _models.HygieneIssue

_detect_broad_exception_patterns = _ast_scanners._detect_broad_exception_patterns
_detect_forbidden_api_usage = _ast_scanners._detect_forbidden_api_usage
_detect_resource_leaks = _ast_scanners._detect_resource_leaks

_detect_runtime_copy_hotspots = _runtime_scanners._detect_runtime_copy_hotspots

_detect_any_type_hints = _text_scanners._detect_any_type_hints
_detect_cleanup_hotspots = _text_scanners._detect_cleanup_hotspots
_detect_defensive_conversions = _text_scanners._detect_defensive_conversions
_detect_forbidden_getattr = _text_scanners._detect_forbidden_getattr
_detect_hasattr_coupling = _text_scanners._detect_hasattr_coupling
_detect_test_naming_issues = _text_scanners._detect_test_naming_issues


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
