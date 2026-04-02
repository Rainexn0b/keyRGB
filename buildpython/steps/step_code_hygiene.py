"""Code hygiene checks for defensive patterns and type discipline.

Detects:
1. Over-defensive type conversions at non-boundary locations
2. hasattr/dynamic attribute coupling (should use typed state objects)
3. Excessive `Any` type hints in core modules
4. Inconsistent test naming patterns
5. Broad exception handler debt split into silent, logged, and fallback buckets
"""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, TypeGuard

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
    "forbidden_getattr": 0,       # New: forbidden getattr/delattr on private attrs
    "forbidden_api": 0,           # New: forbidden API usage
    "resource_leak": 0,           # New: open() without with/context or .close()
    "cleanup_hotspot": 0,         # New: facade/legacy/cleanup marker
    "silent_broad_except": 0,     # New: broad except handlers with no recovery or signal
    "logged_broad_except": 0,     # New: broad except handlers that log or notify
    "fallback_broad_except": 0,   # New: broad except handlers that apply fallback behavior
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

_DEBT_BASELINE_PATH = Path("buildpython/config/debt_baselines.json")

_BASELINE_LOAD_ERRORS = (OSError, json.JSONDecodeError)
_TEXT_READ_ERRORS = (OSError,)
_SOURCE_PARSE_ERRORS = (OSError, SyntaxError, ValueError)


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


@dataclass(frozen=True)
class HygieneBaseline:
    counts: dict[str, int]
    gated_categories: set[str]
    path_budgets: dict[str, dict[str, int]]


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


def _load_hygiene_baseline(root: Path) -> HygieneBaseline:
    config_path = root / _DEBT_BASELINE_PATH
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except _BASELINE_LOAD_ERRORS:
        return HygieneBaseline(counts={}, gated_categories=set(), path_budgets={})

    section = payload.get("code_hygiene", {})
    counts_raw = section.get("counts", {})
    counts = {
        str(category): int(value)
        for category, value in counts_raw.items()
        if isinstance(value, int | float)
    }
    gated_categories = {
        str(category)
        for category in section.get("gated_categories", [])
        if isinstance(category, str)
    }
    path_budgets_raw = section.get("path_budgets", {})
    path_budgets = {
        str(category): {
            str(path): int(value)
            for path, value in budgets.items()
            if isinstance(path, str) and isinstance(value, int | float)
        }
        for category, budgets in path_budgets_raw.items()
        if isinstance(category, str) and isinstance(budgets, dict)
    }
    return HygieneBaseline(counts=counts, gated_categories=gated_categories, path_budgets=path_budgets)


def _baseline_delta(current: int, baseline: int | None) -> str:
    if baseline is None:
        return "n/a"
    delta = current - baseline
    return f"{delta:+d}"


def _baseline_regressions(counts: Counter[str], baseline: HygieneBaseline) -> list[tuple[str, int, int]]:
    regressions: list[tuple[str, int, int]] = []
    for category in sorted(baseline.gated_categories):
        current = counts.get(category, 0)
        expected = baseline.counts.get(category, 0)
        if current > expected:
            regressions.append((category, current, expected))
    return regressions


def _path_budget_regressions(
    issues: list[HygieneIssue],
    baseline: HygieneBaseline,
) -> list[tuple[str, str, int, int]]:
    grouped: dict[str, Counter[str]] = {}
    for issue in issues:
        grouped.setdefault(issue.category, Counter())[issue.path] += 1

    regressions: list[tuple[str, str, int, int]] = []
    for category, budgets in baseline.path_budgets.items():
        current_counts = grouped.get(category, Counter())
        for path, expected in budgets.items():
            current = int(current_counts.get(path, 0))
            if current > expected:
                regressions.append((category, path, current, expected))
    return regressions


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
    except _TEXT_READ_ERRORS:
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
    except _TEXT_READ_ERRORS:
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
    "src/tray/pollers/config_polling_internal/helpers.py": {
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
    except _SOURCE_PARSE_ERRORS:
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
    except _TEXT_READ_ERRORS:
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
    tests_dir = root / "tests"
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
# Forbidden getattr/delattr on private attributes
# ---------------------------------------------------------------------------
_GETATTR_PATTERN = re.compile(r'\bgetattr\s*\(\s*\w+\s*,\s*["\']_')
_DELATTR_PATTERN = re.compile(r'\bdelattr\s*\(\s*\w+\s*,\s*["\']_')
_GETATTR_EXCLUDE_PATHS = ["src/tests/", "tests/"]

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
            issues.append(HygieneIssue(
                category="forbidden_getattr",
                path=rel,
                line=idx,
                message="getattr() on private attr is forbidden - use typed state",
                snippet=line.strip()[:120],
            ))
        if _DELATTR_PATTERN.search(line):
            issues.append(HygieneIssue(
                category="forbidden_getattr",
                path=rel,
                line=idx,
                message="delattr() on private attr is forbidden - use typed state",
                snippet=line.strip()[:120],
            ))
    return issues

# ---------------------------------------------------------------------------
# Forbidden API usage (os.system, eval, exec)
# ---------------------------------------------------------------------------
_FORBIDDEN_API_EXCLUDE_PATHS = ["src/tests/", "tests/"]

def _detect_forbidden_api_usage(path: Path, root: Path) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    rel = str(path.relative_to(root))
    if any(excl in rel for excl in _FORBIDDEN_API_EXCLUDE_PATHS):
        return issues
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
    except _SOURCE_PARSE_ERRORS:
        return issues

    lines = text.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        message = _forbidden_api_message(node)
        if message is None:
            continue
        line = lines[node.lineno - 1].strip() if 0 < node.lineno <= len(lines) else ""
        issues.append(HygieneIssue(
            category="forbidden_api",
            path=rel,
            line=node.lineno,
            message=message,
            snippet=line[:120],
        ))
    return issues


def _forbidden_api_message(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        if call.func.id == "eval":
            return "eval() is forbidden - never use eval in production code"
        if call.func.id == "exec":
            return "exec() is forbidden - never use exec in production code"

    if isinstance(call.func, ast.Attribute):
        if call.func.attr == "system" and isinstance(call.func.value, ast.Name) and call.func.value.id == "os":
            return "os.system() is forbidden - use subprocess.run/check_call"

    return None


# ---------------------------------------------------------------------------
# Resource leak detector: built-in open() without with/context or without .close()
# ---------------------------------------------------------------------------
_RESOURCE_LEAK_EXCLUDE_PATHS = ["src/tests/", "tests/"]

def _detect_resource_leaks(path: Path, root: Path) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    rel = str(path.relative_to(root))
    if any(excl in rel for excl in _RESOURCE_LEAK_EXCLUDE_PATHS):
        return issues
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
    except _SOURCE_PARSE_ERRORS:
        return issues

    lines = text.splitlines()
    parents = _build_parent_map(tree)
    for node in ast.walk(tree):
        if not _is_builtin_open_call(node):
            continue
        if _is_with_context_expr(node, parents):
            continue
        if _has_nearby_close(node=node, parents=parents, lines=lines):
            continue

        line = lines[node.lineno - 1].strip() if 0 < node.lineno <= len(lines) else ""
        issues.append(HygieneIssue(
            category="resource_leak",
            path=rel,
            line=node.lineno,
            message="open() not used in with/context and no nearby .close() found",
            snippet=line[:120],
        ))
    return issues


def _build_parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def _is_builtin_open_call(node: ast.AST) -> TypeGuard[ast.Call]:
    return isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open"


def _is_with_context_expr(node: ast.Call, parents: dict[ast.AST, ast.AST]) -> bool:
    parent = parents.get(node)
    if not isinstance(parent, ast.withitem):
        return False
    return parent.context_expr is node


def _has_nearby_close(*, node: ast.Call, parents: dict[ast.AST, ast.AST], lines: list[str]) -> bool:
    parent = parents.get(node)
    if not isinstance(parent, ast.Assign) or len(parent.targets) != 1:
        return False
    target = parent.targets[0]
    if not isinstance(target, ast.Name):
        return False

    var_name = target.id
    end_line = min(len(lines), node.lineno + 12)
    close_tokens = (f"{var_name}.close()", f"{var_name}.close")
    for idx in range(node.lineno, end_line):
        if any(token in lines[idx] for token in close_tokens):
            return True
    return False


# ---------------------------------------------------------------------------
# Facade/Legacy/Cleanup Hotspot Detector
# ---------------------------------------------------------------------------
_CLEANUP_MARKERS = [
    re.compile(r'#\s*TODO', re.IGNORECASE),
    re.compile(r'#\s*FIXME', re.IGNORECASE),
    re.compile(r'#\s*HACK', re.IGNORECASE),
    re.compile(r'#\s*LEGACY', re.IGNORECASE),
    re.compile(r'#\s*FACADE', re.IGNORECASE),
    re.compile(r'legacy_', re.IGNORECASE),
    re.compile(r'facade_', re.IGNORECASE),
    re.compile(r'migrate_legacy', re.IGNORECASE),
    re.compile(r'compat_', re.IGNORECASE),
]
_CLEANUP_EXCLUDE_PATHS = ["src/tests/", "tests/"]

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
                issues.append(HygieneIssue(
                    category="cleanup_hotspot",
                    path=rel,
                    line=idx,
                    message="Cleanup/facade/legacy marker found: consider refactor or migration plan",
                    snippet=line.strip()[:120],
                ))
    return issues


# ---------------------------------------------------------------------------
# Broad exception handlers
# ---------------------------------------------------------------------------

_BROAD_EXCEPT_EXCLUDE_PATHS = ["src/tests/", "tests/"]

_BROAD_EXCEPTION_MESSAGES = {
    "silent_broad_except": "broad exception handler silently swallows failure - add logging or explicit recovery",
    "logged_broad_except": "broad exception handler logs or signals failure - consider narrowing the exception type",
    "fallback_broad_except": "broad exception handler applies fallback behavior - consider narrowing the exception type",
}


def _detect_broad_exception_patterns(path: Path, root: Path) -> list[HygieneIssue]:
    issues: list[HygieneIssue] = []
    rel = str(path.relative_to(root))

    if any(excl in rel for excl in _BROAD_EXCEPT_EXCLUDE_PATHS):
        return issues

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(text)
    except _SOURCE_PARSE_ERRORS:
        return issues

    lines = text.splitlines()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for handler in node.handlers:
            if not _is_broad_exception_handler(handler):
                continue
            category = _classify_broad_exception_body(handler.body)
            if category is None:
                continue

            line = lines[handler.lineno - 1].strip() if 0 < handler.lineno <= len(lines) else ""
            issues.append(HygieneIssue(
                category=category,
                path=rel,
                line=handler.lineno,
                message=_BROAD_EXCEPTION_MESSAGES[category],
                snippet=line[:120],
            ))

    return issues


def _is_broad_exception_handler(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True

    if isinstance(handler.type, ast.Name):
        return handler.type.id in {"Exception", "BaseException"}

    return False


def _is_silent_exception_body(body: list[ast.stmt]) -> bool:
    if not body:
        return True

    allowed_silent_nodes = (ast.Pass, ast.Break, ast.Continue)
    for stmt in body:
        if isinstance(stmt, allowed_silent_nodes):
            continue
        if isinstance(stmt, ast.Return) and stmt.value is None:
            continue
        return False

    return True


def _classify_broad_exception_body(body: list[ast.stmt]) -> str | None:
    if _contains_reraise(body):
        return None
    if _is_silent_exception_body(body):
        return "silent_broad_except"
    if _contains_exception_signal(body):
        return "logged_broad_except"
    return "fallback_broad_except"


def _contains_reraise(body: list[ast.stmt]) -> bool:
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Raise):
                return True
    return False


def _contains_exception_signal(body: list[ast.stmt]) -> bool:
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and _is_exception_signal_call(node):
                return True
    return False


def _is_exception_signal_call(call: ast.Call) -> bool:
    if isinstance(call.func, ast.Attribute):
        attr_name = call.func.attr.lower()
        if attr_name in {
            "debug",
            "info",
            "warning",
            "warn",
            "error",
            "exception",
            "critical",
            "log",
            "notify",
            "showerror",
            "showwarning",
            "showinfo",
            "_log_exception",
            "log_exception",
        }:
            return True

    if isinstance(call.func, ast.Name):
        func_name = call.func.id.lower()
        return func_name in {"print", "notify", "showerror", "showwarning", "showinfo"}

    return False


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
        all_issues.extend(_detect_forbidden_getattr(p, root))
        all_issues.extend(_detect_forbidden_api_usage(p, root))
        all_issues.extend(_detect_resource_leaks(p, root))
        all_issues.extend(_detect_cleanup_hotspots(p, root))
        all_issues.extend(_detect_broad_exception_patterns(p, root))

    all_issues.extend(_detect_test_naming_issues(root))

    return all_issues


def _build_stdout(issues: list[HygieneIssue], counts: Counter[str], baseline: HygieneBaseline) -> list[str]:
    lines: list[str] = []
    top_files_by_category = _top_files_by_category(issues)
    regressions = _baseline_regressions(counts, baseline)
    path_regressions = _path_budget_regressions(issues, baseline)

    lines.append("Code Hygiene Check")
    lines.append("=" * 40)
    lines.append("")

    lines.append("Issue counts by category:")
    for cat, threshold in CATEGORY_THRESHOLDS.items():
        count = counts.get(cat, 0)
        status = "FAIL" if count > threshold else "OK"
        baseline_count = baseline.counts.get(cat)
        delta = _baseline_delta(count, baseline_count)
        baseline_text = "-" if baseline_count is None else str(baseline_count)
        lines.append(f"  {cat:<25} {count:>4} / {threshold:<4} baseline={baseline_text:<4} delta={delta:<4} [{status}]")

    lines.append("")
    lines.append(f"Total issues: {len(issues)}")

    if regressions:
        lines.append("")
        lines.append("Regression-gated debt increases:")
        for category, current, expected in regressions:
            lines.append(f"  {category}: {current} > baseline {expected}")

    if path_regressions:
        lines.append("")
        lines.append("Per-path exception budget regressions:")
        for category, path, current, expected in path_regressions:
            lines.append(f"  {category} {path}: {current} > budget {expected}")

    for category, title in [
        ("silent_broad_except", "Silent exception debt hotspots"),
        ("logged_broad_except", "Logged exception debt hotspots"),
        ("fallback_broad_except", "Fallback exception debt hotspots"),
        ("cleanup_hotspot", "Cleanup debt hotspots"),
        ("forbidden_api", "Forbidden API hotspots"),
    ]:
        hotspots = top_files_by_category.get(category, [])
        if not hotspots:
            continue
        lines.append("")
        lines.append(f"{title}:")
        for path, count in hotspots[:10]:
            lines.append(f"  {count:>3}  {path}")

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


def _top_files_by_category(issues: list[HygieneIssue]) -> dict[str, list[tuple[str, int]]]:
    grouped: dict[str, Counter[str]] = {}
    for issue in issues:
        counter = grouped.setdefault(issue.category, Counter())
        counter[issue.path] += 1

    return {
        category: counter.most_common(20)
        for category, counter in grouped.items()
    }


def _write_reports(root: Path, issues: list[HygieneIssue], counts: Counter[str], baseline: HygieneBaseline) -> None:
    report_dir = root / "buildlog" / "keyrgb"
    report_dir.mkdir(parents=True, exist_ok=True)

    report_json = report_dir / "code-hygiene.json"
    report_csv = report_dir / "code-hygiene.csv"
    report_md = report_dir / "code-hygiene.md"
    top_files_by_category = _top_files_by_category(issues)
    regressions = _baseline_regressions(counts, baseline)
    path_regressions = _path_budget_regressions(issues, baseline)

    # JSON
    data = {
        "thresholds": dict(CATEGORY_THRESHOLDS),
        "counts": dict(counts),
        "total": len(issues),
        "baseline": {
            "counts": baseline.counts,
            "gated_categories": sorted(baseline.gated_categories),
            "path_budgets": baseline.path_budgets,
            "regressions": [
                {"category": category, "current": current, "baseline": expected}
                for category, current, expected in regressions
            ],
            "path_budget_regressions": [
                {
                    "category": category,
                    "path": path,
                    "current": current,
                    "baseline": expected,
                }
                for category, path, current, expected in path_regressions
            ],
        },
        "top_files_by_category": {
            category: [
                {"path": path, "count": count}
                for path, count in file_counts
            ]
            for category, file_counts in top_files_by_category.items()
        },
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
        "| Category | Count | Threshold | Baseline | Delta | Status |",
        "|----------|------:|----------:|---------:|------:|--------|",
    ]
    for cat, threshold in CATEGORY_THRESHOLDS.items():
        count = counts.get(cat, 0)
        status = "❌ FAIL" if count > threshold else "✅ OK"
        baseline_count = baseline.counts.get(cat)
        baseline_text = "-" if baseline_count is None else str(baseline_count)
        delta = _baseline_delta(count, baseline_count)
        md_lines.append(f"| {cat} | {count} | {threshold} | {baseline_text} | {delta} | {status} |")

    md_lines.extend(["", f"**Total issues:** {len(issues)}", ""])

    if regressions:
        md_lines.extend(["## Regression-Gated Debt Increases", ""])
        md_lines.append("| Category | Current | Baseline |")
        md_lines.append("|----------|--------:|---------:|")
        for category, current, expected in regressions:
            md_lines.append(f"| {category} | {current} | {expected} |")
        md_lines.append("")

    if path_regressions:
        md_lines.extend(["## Per-Path Exception Budget Regressions", ""])
        md_lines.append("| Category | Path | Current | Budget |")
        md_lines.append("|----------|------|--------:|-------:|")
        for category, path, current, expected in path_regressions:
            md_lines.append(f"| {category} | {path} | {current} | {expected} |")
        md_lines.append("")

    for category, title in [
        ("silent_broad_except", "Silent Exception Debt Hotspots"),
        ("logged_broad_except", "Logged Exception Debt Hotspots"),
        ("fallback_broad_except", "Fallback Exception Debt Hotspots"),
        ("cleanup_hotspot", "Cleanup Debt Hotspots"),
        ("forbidden_api", "Forbidden API Hotspots"),
        ("resource_leak", "Resource Leak Hotspots"),
    ]:
        hotspots = top_files_by_category.get(category, [])
        if not hotspots:
            continue
        md_lines.extend([f"## {title}", ""])
        md_lines.append("| File | Count |")
        md_lines.append("|------|------:|")
        for path, count in hotspots[:15]:
            md_lines.append(f"| {path} | {count} |")
        md_lines.append("")

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
    baseline = _load_hygiene_baseline(root)

    counts: Counter[str] = Counter()
    for issue in issues:
        counts[issue.category] += 1

    stdout_lines = _build_stdout(issues, counts, baseline)
    _write_reports(root, issues, counts, baseline)

    # Determine if we should fail
    should_fail = False
    if FAIL_THRESHOLD_TOTAL > 0 and len(issues) > FAIL_THRESHOLD_TOTAL:
        should_fail = True

    for cat, threshold in CATEGORY_THRESHOLDS.items():
        if threshold > 0 and counts.get(cat, 0) > threshold:
            should_fail = True
            break

    if _baseline_regressions(counts, baseline):
        should_fail = True

    if _path_budget_regressions(issues, baseline):
        should_fail = True

    exit_code = 1 if should_fail else 0

    return RunResult(
        command_str="(internal) code hygiene check",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=exit_code,
    )
