"""Code hygiene checks for defensive patterns and type discipline.

Detects:
1. Over-defensive type conversions at non-boundary locations
2. hasattr/dynamic attribute coupling (should use typed state objects)
3. Excessive `Any` type hints in core modules
4. Inconsistent test naming patterns
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..utils.paths import repo_root
from ..utils.subproc import RunResult
from .reports import write_csv, write_json, write_md


# ---------------------------------------------------------------------------
# Configuration / thresholds
# ---------------------------------------------------------------------------

# Fail build if total issues exceed this (0 = report only, never fail)
FAIL_THRESHOLD_TOTAL = 0  # Start as report-only; tighten later

# Fail if any single category exceeds its threshold
# Thresholds are set close to current baseline counts to allow minor
# fluctuations but catch regressions.
CATEGORY_THRESHOLDS = {
    "defensive_conversion": 50,   # Current: 48 - migrate to safe_attrs over time
    "hasattr_coupling": 22,       # Current: 20 - migrate to typed state objects over time
    "any_type_hint": 66,          # Current: 64 - add Protocol types over time
    "runtime_copy_hotspot": 0,    # Report-only until the baseline is tightened
    "test_naming": 0,             # Fixed - no new violations allowed
}

# Paths to exclude from analysis (vendor code, generated, etc.)
EXCLUDE_PATTERNS = [
    "vendor/",
    "__pycache__/",
    ".git/",
    "htmlcov/",
    "buildlog/",
    ".venv/",
]


# ---------------------------------------------------------------------------
# Issue types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HygieneIssue:
    category: str
    path: str
    line: int
    message: str
    snippet: str


# ---------------------------------------------------------------------------
# Detectors
# ---------------------------------------------------------------------------

def _should_exclude(path: Path, root: Path) -> bool:
    rel = str(path.relative_to(root))
    return any(excl in rel for excl in EXCLUDE_PATTERNS)


def _iter_python_files(root: Path) -> Iterable[Path]:
    for folder in [root / "src", root / "buildpython"]:
        if not folder.exists():
            continue
        for p in folder.rglob("*.py"):
            if _should_exclude(p, root):
                continue
            yield p


# ---------------------------------------------------------------------------
# 1. Over-defensive type conversions
# ---------------------------------------------------------------------------

# Pattern: int(int(x)) or int(x) where x is already guaranteed int
# Also: excessive int(getattr(...)) chains
_DEFENSIVE_PATTERNS = [
    # Nested conversions: int(int(x)), bool(bool(x))
    (re.compile(r"\bint\s*\(\s*int\s*\("), "nested int(int(...))"),
    (re.compile(r"\bbool\s*\(\s*bool\s*\("), "nested bool(bool(...))"),
    (re.compile(r"\bfloat\s*\(\s*float\s*\("), "nested float(float(...))"),
    (re.compile(r"\bstr\s*\(\s*str\s*\("), "nested str(str(...))"),
    # Triple defensive: int(getattr(..., 0) or 0)
    (re.compile(r"\bint\s*\(\s*getattr\s*\([^)]+\)\s*or\s*0\s*\)"), "int(getattr(...) or 0) - consider default param"),
    # Explicit int() on already-int arithmetic
    (re.compile(r"return\s+int\s*\(\s*int\s*\("), "return int(int(...))"),
]


def _detect_defensive_conversions(path: Path, root: Path) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return issues

    rel = str(path.relative_to(root))
    for idx, line in enumerate(text.splitlines(), start=1):
        for pattern, desc in _DEFENSIVE_PATTERNS:
            if pattern.search(line):
                issues.append(HygieneIssue(
                    category="defensive_conversion",
                    path=rel,
                    line=idx,
                    message=desc,
                    snippet=line.strip()[:120],
                ))
    return issues


# ---------------------------------------------------------------------------
# 2. hasattr / dynamic attribute coupling
# ---------------------------------------------------------------------------

# Pattern: hasattr(obj, "_private_attr") followed by setattr or direct access
_HASATTR_PATTERN = re.compile(r'\bhasattr\s*\(\s*\w+\s*,\s*["\']_')
_SETATTR_PATTERN = re.compile(r'\bsetattr\s*\(\s*\w+\s*,\s*["\']_')

# Paths where hasattr/setattr is expected (tests use monkeypatch legitimately)
_HASATTR_EXCLUDE_PATHS = ["src/tests/", "tests/"]


def _detect_hasattr_coupling(path: Path, root: Path) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    rel = str(path.relative_to(root))

    # Skip test files - monkeypatch.setattr is idiomatic in tests
    if any(excl in rel for excl in _HASATTR_EXCLUDE_PATHS):
        return issues

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return issues

    lines = text.splitlines()

    for idx, line in enumerate(lines, start=1):
        if _HASATTR_PATTERN.search(line):
            issues.append(HygieneIssue(
                category="hasattr_coupling",
                path=rel,
                line=idx,
                message="hasattr() on private attr - consider typed state object",
                snippet=line.strip()[:120],
            ))
        # Also flag setattr to private attrs (usually paired with hasattr)
        if _SETATTR_PATTERN.search(line):
            issues.append(HygieneIssue(
                category="hasattr_coupling",
                path=rel,
                line=idx,
                message="setattr() on private attr - consider typed state object",
                snippet=line.strip()[:120],
            ))

    return issues


# ---------------------------------------------------------------------------
# 3. Excessive Any type hints
# ---------------------------------------------------------------------------

# Only check core modules (not tests, not GUI which often needs Any for Tk)
_ANY_CHECK_PATHS = ["src/core/", "src/tray/controllers/", "src/tray/pollers/"]


# ---------------------------------------------------------------------------
# 4. Runtime copy hotspots
# ---------------------------------------------------------------------------

_RUNTIME_COPY_WATCH_PATHS = [
    "src/core/effects/",
    "src/tray/controllers/",
    "src/tray/pollers/",
    "src/tray/ui/",
]

_RUNTIME_COPY_FUNCTION_PREFIXES = (
    "run_",
    "render",
    "apply_",
    "_apply_",
    "create_",
    "_create_",
    "draw_",
    "redraw_",
    "refresh_",
    "update_",
    "start_",
    "_start_",
    "poll_",
    "_poll_",
)

_RUNTIME_COPY_SOURCE_TOKENS = (
    "per_key",
    "color_map",
    "colors",
    "overlay",
    "frame",
    "base",
    "target",
    "map",
    "image",
    "icon",
    "backdrop",
    "underlay",
    "pulse",
)

_RUNTIME_COPY_IGNORE_SNIPPETS: dict[str, set[str]] = {
    "src/core/effects/reactive/render.py": {
        "dict(color_map)",
        "color_map",
    },
    "src/tray/pollers/_config_polling_helpers.py": {
        "dict(configured_map)",
        "configured_map",
    },
    "src/tray/ui/icon_draw.py": {
        "_rainbow_gradient_64(phase_q).copy()",
        "underlay.copy()",
        "underlay",
    },
}

_LOOP_NODES = (ast.For, ast.AsyncFor, ast.While)


def _detect_runtime_copy_hotspots(path: Path, root: Path) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    rel = str(path.relative_to(root))

    if not any(rel.startswith(prefix) for prefix in _RUNTIME_COPY_WATCH_PATHS):
        return issues

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
    except Exception:
        return issues

    lines = text.splitlines()
    ignore_snippets = _RUNTIME_COPY_IGNORE_SNIPPETS.get(rel, set())

    def visit(node: ast.AST, *, current_function: str | None, loop_depth: int) -> None:
        next_function = current_function
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            next_function = node.name

        next_loop_depth = loop_depth + 1 if isinstance(node, _LOOP_NODES) else loop_depth

        if isinstance(node, ast.Call):
            issue = _runtime_copy_issue_for_call(
                call=node,
                rel=rel,
                text=text,
                lines=lines,
                current_function=next_function,
                loop_depth=next_loop_depth,
                ignore_snippets=ignore_snippets,
            )
            if issue is not None:
                issues.append(issue)

        for child in ast.iter_child_nodes(node):
            visit(child, current_function=next_function, loop_depth=next_loop_depth)

    visit(tree, current_function=None, loop_depth=0)
    return issues


def _runtime_copy_issue_for_call(
    *,
    call: ast.Call,
    rel: str,
    text: str,
    lines: list[str],
    current_function: str | None,
    loop_depth: int,
    ignore_snippets: set[str],
) -> HygieneIssue | None:
    if current_function is None:
        return None

    if loop_depth <= 0 and not _is_runtime_hot_function(current_function):
        return None

    copy_kind, source_text, call_text = _runtime_copy_signature(call=call, text=text)
    if copy_kind is None or source_text is None or call_text is None:
        return None

    if source_text in ignore_snippets or call_text in ignore_snippets:
        return None

    source_lower = source_text.lower()
    if not any(token in source_lower for token in _RUNTIME_COPY_SOURCE_TOKENS):
        return None

    line = lines[call.lineno - 1].strip() if 0 < call.lineno <= len(lines) else ""
    return HygieneIssue(
        category="runtime_copy_hotspot",
        path=rel,
        line=call.lineno,
        message=(
            f"{copy_kind} inside runtime path `{current_function}` on `{source_text}` - "
            "consider reference reuse or reusable buffers"
        ),
        snippet=line[:120],
    )


def _runtime_copy_signature(*, call: ast.Call, text: str) -> tuple[str | None, str | None, str | None]:
    call_text = ast.get_source_segment(text, call) or ast.unparse(call)

    if isinstance(call.func, ast.Name) and call.func.id == "dict" and len(call.args) == 1 and not call.keywords:
        source = ast.get_source_segment(text, call.args[0]) or ast.unparse(call.args[0])
        return "dict(...) copy", source, call_text

    if isinstance(call.func, ast.Attribute) and call.func.attr == "copy" and not call.args and not call.keywords:
        source = ast.get_source_segment(text, call.func.value) or ast.unparse(call.func.value)
        return ".copy() clone", source, call_text

    return None, None, None


def _is_runtime_hot_function(name: str) -> bool:
    lowered = name.lower()
    return any(lowered.startswith(prefix) for prefix in _RUNTIME_COPY_FUNCTION_PREFIXES)


def _detect_any_type_hints(path: Path, root: Path) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    rel = str(path.relative_to(root))

    # Only check specific paths
    if not any(check_path in rel for check_path in _ANY_CHECK_PATHS):
        return issues

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return issues

    # Pattern: function parameter with : Any or -> Any
    any_param = re.compile(r':\s*Any\b(?!\[)')  # Any but not Any[...]
    any_return = re.compile(r'->\s*Any\b(?!\[)')

    for idx, line in enumerate(text.splitlines(), start=1):
        # Skip imports
        if "from typing import" in line or "import typing" in line:
            continue
        # Skip comments
        stripped = line.lstrip()
        if stripped.startswith("#"):
            continue

        if any_param.search(line):
            issues.append(HygieneIssue(
                category="any_type_hint",
                path=rel,
                line=idx,
                message="Parameter typed as Any - consider Protocol or concrete type",
                snippet=line.strip()[:120],
            ))
        if any_return.search(line):
            issues.append(HygieneIssue(
                category="any_type_hint",
                path=rel,
                line=idx,
                message="Return typed as Any - consider Protocol or concrete type",
                snippet=line.strip()[:120],
            ))

    return issues


# ---------------------------------------------------------------------------
# 5. Inconsistent test naming
# ---------------------------------------------------------------------------

# Expected: test_<module>_<aspect>_unit.py or test_<module>_<aspect>_integration.py
_TEST_NAME_PATTERN = re.compile(r'^test_[a-z0-9_]+_(unit|integration|e2e)\.py$')


def _detect_test_naming_issues(root: Path) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    tests_dir = root / "src" / "tests"
    if not tests_dir.exists():
        return issues

    for p in tests_dir.glob("test_*.py"):
        if not _TEST_NAME_PATTERN.match(p.name):
            issues.append(HygieneIssue(
                category="test_naming",
                path=str(p.relative_to(root)),
                line=0,
                message=f"Test file should end with _unit.py, _integration.py, or _e2e.py",
                snippet=p.name,
            ))

    return issues


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def _collect_all_issues(root: Path) -> list[HygieneIssue]:
    all_issues: list[HygieneIssue] = []

    for p in _iter_python_files(root):
        all_issues.extend(_detect_defensive_conversions(p, root))
        all_issues.extend(_detect_hasattr_coupling(p, root))
        all_issues.extend(_detect_any_type_hints(p, root))
        all_issues.extend(_detect_runtime_copy_hotspots(p, root))

    all_issues.extend(_detect_test_naming_issues(root))

    return all_issues


def _build_stdout(issues: list[HygieneIssue], counts: Counter[str]) -> list[str]:
    lines: list[str] = []
    lines.append("Code Hygiene Check")
    lines.append("=" * 40)
    lines.append("")

    lines.append("Issue counts by category:")
    for cat, threshold in CATEGORY_THRESHOLDS.items():
        count = counts.get(cat, 0)
        status = "FAIL" if count > threshold else "OK"
        lines.append(f"  {cat:<25} {count:>4} / {threshold:<4} [{status}]")

    lines.append("")
    lines.append(f"Total issues: {len(issues)}")

    if issues:
        lines.append("")
        lines.append("Sample issues (first 50):")
        for issue in issues[:50]:
            loc = f"{issue.path}:{issue.line}" if issue.line else issue.path
            lines.append(f"  [{issue.category}] {loc}")
            lines.append(f"    {issue.message}")
            if issue.snippet:
                lines.append(f"    > {issue.snippet[:80]}")

    return lines


def _write_reports(root: Path, issues: list[HygieneIssue], counts: Counter[str]) -> None:
    report_dir = root / "buildlog" / "keyrgb"
    report_dir.mkdir(parents=True, exist_ok=True)

    report_json = report_dir / "code-hygiene.json"
    report_csv = report_dir / "code-hygiene.csv"
    report_md = report_dir / "code-hygiene.md"

    # JSON
    data = {
        "thresholds": dict(CATEGORY_THRESHOLDS),
        "counts": dict(counts),
        "total": len(issues),
        "issues": [
            {
                "category": i.category,
                "path": i.path,
                "line": i.line,
                "message": i.message,
                "snippet": i.snippet,
            }
            for i in issues[:500]
        ],
    }
    write_json(report_json, data)

    # CSV
    write_csv(
        report_csv,
        ["category", "path", "line", "message", "snippet"],
        [[i.category, i.path, str(i.line), i.message, i.snippet] for i in issues[:500]],
    )

    # Markdown
    md_lines: list[str] = [
        "# Code Hygiene Report",
        "",
        "## Summary",
        "",
        "| Category | Count | Threshold | Status |",
        "|----------|------:|----------:|--------|",
    ]
    for cat, threshold in CATEGORY_THRESHOLDS.items():
        count = counts.get(cat, 0)
        status = "❌ FAIL" if count > threshold else "✅ OK"
        md_lines.append(f"| {cat} | {count} | {threshold} | {status} |")

    md_lines.extend(["", f"**Total issues:** {len(issues)}", ""])

    if issues:
        md_lines.extend(["## Issues (sample)", ""])
        for issue in issues[:100]:
            loc = f"{issue.path}:{issue.line}" if issue.line else issue.path
            md_lines.append(f"### `{issue.category}` at {loc}")
            md_lines.append(f"")
            md_lines.append(f"**{issue.message}**")
            if issue.snippet:
                md_lines.append(f"```python")
                md_lines.append(issue.snippet)
                md_lines.append(f"```")
            md_lines.append("")

    write_md(report_md, md_lines)


def code_hygiene_runner() -> RunResult:
    root = repo_root()
    issues = _collect_all_issues(root)

    counts: Counter[str] = Counter()
    for issue in issues:
        counts[issue.category] += 1

    stdout_lines = _build_stdout(issues, counts)
    _write_reports(root, issues, counts)

    # Determine if we should fail
    should_fail = False
    if FAIL_THRESHOLD_TOTAL > 0 and len(issues) > FAIL_THRESHOLD_TOTAL:
        should_fail = True

    for cat, threshold in CATEGORY_THRESHOLDS.items():
        if threshold > 0 and counts.get(cat, 0) > threshold:
            should_fail = True
            break

    exit_code = 1 if should_fail else 0

    return RunResult(
        command_str="(internal) code hygiene check",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=exit_code,
    )
