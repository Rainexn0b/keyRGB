from __future__ import annotations

import ast
from pathlib import Path
from typing import TypeGuard

from .models import HygieneIssue


_SOURCE_PARSE_ERRORS = (OSError, SyntaxError, ValueError)

_FORBIDDEN_API_EXCLUDE_PATHS = ["src/tests/", "tests/"]
_RESOURCE_LEAK_EXCLUDE_PATHS = ["src/tests/", "tests/"]
_BROAD_EXCEPT_EXCLUDE_PATHS = ["src/tests/", "tests/"]

_BROAD_EXCEPTION_MESSAGES = {
    "silent_broad_except": "broad exception handler silently swallows failure - add logging or explicit recovery",
    "logged_broad_except": "broad exception handler logs or signals failure - consider narrowing the exception type",
    "fallback_broad_except": "broad exception handler applies fallback behavior - consider narrowing the exception type",
}


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
        issues.append(
            HygieneIssue(
                category="forbidden_api",
                path=rel,
                line=node.lineno,
                message=message,
                snippet=line[:120],
            )
        )
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
        issues.append(
            HygieneIssue(
                category="resource_leak",
                path=rel,
                line=node.lineno,
                message="open() not used in with/context and no nearby .close() found",
                snippet=line[:120],
            )
        )
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
            raw_line = lines[handler.lineno - 1] if 0 < handler.lineno <= len(lines) else ""
            is_suppressed = "@quality-exception" in raw_line
            issues.append(
                HygieneIssue(
                    category=category,
                    path=rel,
                    line=handler.lineno,
                    message=_BROAD_EXCEPTION_MESSAGES[category],
                    snippet=line[:120],
                    suppressed=is_suppressed,
                )
            )

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
