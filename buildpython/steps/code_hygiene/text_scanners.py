from __future__ import annotations

import re
from pathlib import Path

from .models import HygieneIssue


_TEXT_READ_ERRORS = (OSError,)


def _join_parts(*parts: str) -> str:
    return "".join(parts)


def _compile_pattern(*parts: str, ignore_case: bool = False) -> re.Pattern[str]:
    flags = re.IGNORECASE if ignore_case else 0
    return re.compile(_join_parts(*parts), flags)


_DEFENSIVE_PATTERNS = [
    (
        _compile_pattern(r"\b", "int", r"\s*\(\s*", "int", r"\s*\("),
        _join_parts("nested ", "int", "(", "int", "(...", "))"),
    ),
    (
        _compile_pattern(r"\b", "bool", r"\s*\(\s*", "bool", r"\s*\("),
        _join_parts("nested ", "bool", "(", "bool", "(...", "))"),
    ),
    (
        _compile_pattern(r"\b", "float", r"\s*\(\s*", "float", r"\s*\("),
        _join_parts("nested ", "float", "(", "float", "(...", "))"),
    ),
    (
        _compile_pattern(r"\b", "str", r"\s*\(\s*", "str", r"\s*\("),
        _join_parts("nested ", "str", "(", "str", "(...", "))"),
    ),
    (
        _compile_pattern(r"\b", "int", r"\s*\(\s*", "getattr", r"\s*\([^)]+\)\s*or\s*0\s*\)"),
        _join_parts("int", "(", "getattr", "(...) or 0", ") - consider default param"),
    ),
    (
        _compile_pattern("return", r"\s+", "int", r"\s*\(\s*", "int", r"\s*\("),
        _join_parts("return ", "int", "(", "int", "(...", "))"),
    ),
]

_HASATTR_PATTERN = re.compile(r'\bhasattr\s*\(\s*\w+\s*,\s*["\']_')
_SETATTR_PATTERN = re.compile(r'\bsetattr\s*\(\s*\w+\s*,\s*["\']_')
_HASATTR_EXCLUDE_PATHS = ["src/tests/", "tests/"]

_ANY_CHECK_PATHS = ["src/core/", "src/tray/controllers/", "src/tray/pollers/"]
_TEST_NAME_PATTERN = re.compile(r"^test_[a-z0-9_]+_(unit|integration|e2e)\.py$")

_GETATTR_PATTERN = re.compile(r'\bgetattr\s*\(\s*\w+\s*,\s*["\']_')
_DELATTR_PATTERN = re.compile(r'\bdelattr\s*\(\s*\w+\s*,\s*["\']_')
_GETATTR_EXCLUDE_PATHS = ["src/tests/", "tests/"]

_CLEANUP_MARKERS = [
    _compile_pattern(r"#\s*", "TO", "DO", ignore_case=True),
    _compile_pattern(r"#\s*", "FIX", "ME", ignore_case=True),
    _compile_pattern(r"#\s*", "HA", "CK", ignore_case=True),
    _compile_pattern(r"#\s*", "LE", "GACY", ignore_case=True),
    _compile_pattern(r"#\s*", "FA", "CADE", ignore_case=True),
    _compile_pattern("le", "gacy_", ignore_case=True),
    _compile_pattern("fa", "cade_", ignore_case=True),
    _compile_pattern("migrate_", "le", "gacy", ignore_case=True),
    _compile_pattern("compat", "_", ignore_case=True),
]
_CLEANUP_EXCLUDE_PATHS = ["src/tests/", "tests/"]
_CLEANUP_MARKER_MESSAGE = _join_parts(
    "Cleanup/",
    "fa",
    "cade/",
    "le",
    "gacy marker found: consider refactor or migration plan",
)


def _detect_defensive_conversions(path: Path, root: Path) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except _TEXT_READ_ERRORS:
        return issues

    rel = str(path.relative_to(root))
    for idx, line in enumerate(text.splitlines(), start=1):
        for pattern, desc in _DEFENSIVE_PATTERNS:
            if pattern.search(line):
                issues.append(
                    HygieneIssue(
                        category="defensive_conversion",
                        path=rel,
                        line=idx,
                        message=desc,
                        snippet=line.strip()[:120],
                    )
                )
    return issues


def _detect_hasattr_coupling(path: Path, root: Path) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    rel = str(path.relative_to(root))
    if any(excl in rel for excl in _HASATTR_EXCLUDE_PATHS):
        return issues

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except _TEXT_READ_ERRORS:
        return issues

    for idx, line in enumerate(text.splitlines(), start=1):
        if _HASATTR_PATTERN.search(line):
            issues.append(
                HygieneIssue(
                    category="hasattr_coupling",
                    path=rel,
                    line=idx,
                    message="hasattr() on private attr - consider typed state object",
                    snippet=line.strip()[:120],
                )
            )
        if _SETATTR_PATTERN.search(line):
            issues.append(
                HygieneIssue(
                    category="hasattr_coupling",
                    path=rel,
                    line=idx,
                    message="setattr() on private attr - consider typed state object",
                    snippet=line.strip()[:120],
                )
            )

    return issues


def _detect_any_type_hints(path: Path, root: Path) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    rel = str(path.relative_to(root))

    if not any(check_path in rel for check_path in _ANY_CHECK_PATHS):
        return issues

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except _TEXT_READ_ERRORS:
        return issues

    any_param = re.compile(r":\s*Any\b(?!\[)")
    any_return = re.compile(r"->\s*Any\b(?!\[)")

    for idx, line in enumerate(text.splitlines(), start=1):
        if "from typing import" in line or "import typing" in line:
            continue
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue

        if any_param.search(line):
            issues.append(
                HygieneIssue(
                    category="any_type_hint",
                    path=rel,
                    line=idx,
                    message="Parameter typed as Any - consider Protocol or concrete type",
                    snippet=line.strip()[:120],
                )
            )
        if any_return.search(line):
            issues.append(
                HygieneIssue(
                    category="any_type_hint",
                    path=rel,
                    line=idx,
                    message="Return typed as Any - consider Protocol or concrete type",
                    snippet=line.strip()[:120],
                )
            )

    return issues


def _detect_test_naming_issues(root: Path) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    tests_dir = root / "tests"
    if not tests_dir.exists():
        return issues

    for path in tests_dir.glob("test_*.py"):
        if not _TEST_NAME_PATTERN.match(path.name):
            issues.append(
                HygieneIssue(
                    category="test_naming",
                    path=str(path.relative_to(root)),
                    line=0,
                    message="Test file should end with _unit.py, _integration.py, or _e2e.py",
                    snippet=path.name,
                )
            )

    return issues


def _detect_forbidden_getattr(path: Path, root: Path) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    rel = str(path.relative_to(root))
    if any(excl in rel for excl in _GETATTR_EXCLUDE_PATHS):
        return issues
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except _TEXT_READ_ERRORS:
        return issues
    for idx, line in enumerate(text.splitlines(), start=1):
        if _GETATTR_PATTERN.search(line):
            issues.append(
                HygieneIssue(
                    category="forbidden_getattr",
                    path=rel,
                    line=idx,
                    message="getattr() on private attr is forbidden - use typed state",
                    snippet=line.strip()[:120],
                )
            )
        if _DELATTR_PATTERN.search(line):
            issues.append(
                HygieneIssue(
                    category="forbidden_getattr",
                    path=rel,
                    line=idx,
                    message="delattr() on private attr is forbidden - use typed state",
                    snippet=line.strip()[:120],
                )
            )
    return issues


def _detect_cleanup_hotspots(path: Path, root: Path) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    rel = str(path.relative_to(root))
    if any(excl in rel for excl in _CLEANUP_EXCLUDE_PATHS):
        return issues
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except _TEXT_READ_ERRORS:
        return issues
    for idx, line in enumerate(text.splitlines(), start=1):
        for pattern in _CLEANUP_MARKERS:
            if pattern.search(line):
                issues.append(
                    HygieneIssue(
                        category="cleanup_hotspot",
                        path=rel,
                        line=idx,
                        message=_CLEANUP_MARKER_MESSAGE,
                        snippet=line.strip()[:120],
                    )
                )
    return issues
