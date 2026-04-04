from __future__ import annotations

import re
from pathlib import Path

from .models import HygieneIssue


_TEXT_READ_ERRORS = (OSError,)

_DEFENSIVE_PATTERNS = [
    (re.compile(r"\bint\s*\(\s*int\s*\("), "nested int(int(...))"),
    (re.compile(r"\bbool\s*\(\s*bool\s*\("), "nested bool(bool(...))"),
    (re.compile(r"\bfloat\s*\(\s*float\s*\("), "nested float(float(...))"),
    (re.compile(r"\bstr\s*\(\s*str\s*\("), "nested str(str(...))"),
    (re.compile(r"\bint\s*\(\s*getattr\s*\([^)]+\)\s*or\s*0\s*\)"), "int(getattr(...) or 0) - consider default param"),
    (re.compile(r"return\s+int\s*\(\s*int\s*\("), "return int(int(...))"),
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
    re.compile(r"#\s*TODO", re.IGNORECASE),
    re.compile(r"#\s*FIXME", re.IGNORECASE),
    re.compile(r"#\s*HACK", re.IGNORECASE),
    re.compile(r"#\s*LEGACY", re.IGNORECASE),
    re.compile(r"#\s*FACADE", re.IGNORECASE),
    re.compile(r"legacy_", re.IGNORECASE),
    re.compile(r"facade_", re.IGNORECASE),
    re.compile(r"migrate_legacy", re.IGNORECASE),
    re.compile(r"compat_", re.IGNORECASE),
]
_CLEANUP_EXCLUDE_PATHS = ["src/tests/", "tests/"]


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
                        message="Cleanup/facade/legacy marker found: consider refactor or migration plan",
                        snippet=line.strip()[:120],
                    )
                )
    return issues
