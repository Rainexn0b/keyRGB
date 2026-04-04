from __future__ import annotations

import ast
from pathlib import Path

from ..quality_exceptions import explanation_for_quality_exception_step
from .baseline import iter_python_files
from .models import ExceptionTransparencyFinding


MESSAGE_BY_CATEGORY = {
    "naked_except": "Naked except catches KeyboardInterrupt/SystemExit; replace it with a specific exception type.",
    "baseexception_catch": "BaseException catch is too broad for normal control flow.",
    "broad_except_total": "Broad exception catch; prefer specific exception types where possible.",
    "broad_except_traceback_logged": "Broad exception catch records a traceback; still a narrowing candidate.",
    "broad_except_logged_no_traceback": "Broad exception catch signals failure without recording a traceback.",
    "broad_except_unlogged": "Broad exception catch suppresses failure without a diagnostic footprint.",
}

TRACEBACK_SIGNAL_NAMES = {"log_exception", "_log_exception"}
QUALITY_EXCEPTION_STEP_SLUG = "exception-transparency"
SIGNAL_NAME_CALLS = {
    "print",
    "notify",
    "showerror",
    "showwarning",
    "showinfo",
    "log_throttled",
    "log_exception",
    "_log_exception",
}
SIGNAL_ATTRS = {
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
    "log_exception",
    "_log_exception",
}
_PARSE_SKIP_EXCEPTIONS = (SyntaxError, ValueError)
_SOURCE_READ_SKIP_EXCEPTIONS = (OSError,)


def handler_type_names(node: ast.expr | None) -> set[str]:
    if node is None:
        return set()
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Attribute):
        return {node.attr}
    if isinstance(node, ast.Tuple):
        names: set[str] = set()
        for element in node.elts:
            names.update(handler_type_names(element))
        return names
    return set()


def is_broad_handler(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    names = handler_type_names(handler.type)
    return bool(names & {"Exception", "BaseException"})


def contains_reraise(body: list[ast.stmt]) -> bool:
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Raise):
                return True
    return False


def has_exc_info_keyword(call: ast.Call) -> bool:
    for keyword in call.keywords:
        if keyword.arg != "exc_info":
            continue
        value = keyword.value
        if isinstance(value, ast.Constant) and value.value is True:
            return True
        if isinstance(value, ast.NameConstant) and value.value is True:
            return True
    return False


def has_named_exception_keyword(call: ast.Call, keyword_name: str) -> bool:
    for keyword in call.keywords:
        if keyword.arg != keyword_name:
            continue
        value = keyword.value
        if isinstance(value, ast.Constant):
            return value.value is not None
        return True
    return False


def is_traceback_logging_call(call: ast.Call) -> bool:
    if isinstance(call.func, ast.Attribute):
        attr_name = call.func.attr.lower()
        if attr_name == "exception":
            return True
        if attr_name in {"error", "critical", "log"} and has_exc_info_keyword(call):
            return True
        return attr_name in TRACEBACK_SIGNAL_NAMES

    if isinstance(call.func, ast.Name):
        func_name = call.func.id.lower()
        if func_name == "log_throttled":
            return has_named_exception_keyword(call, "exc")
        return func_name in TRACEBACK_SIGNAL_NAMES

    return False


def is_signal_call(call: ast.Call) -> bool:
    if is_traceback_logging_call(call):
        return True

    if isinstance(call.func, ast.Attribute):
        return call.func.attr.lower() in SIGNAL_ATTRS

    if isinstance(call.func, ast.Name):
        return call.func.id.lower() in SIGNAL_NAME_CALLS

    return False


def contains_traceback_logging(body: list[ast.stmt]) -> bool:
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and is_traceback_logging_call(node):
                return True
    return False


def contains_signal(body: list[ast.stmt]) -> bool:
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and is_signal_call(node):
                return True
    return False


def make_finding(
    category: str, rel_path: str, handler: ast.ExceptHandler, lines: list[str]
) -> ExceptionTransparencyFinding:
    snippet = lines[handler.lineno - 1].strip() if 0 < handler.lineno <= len(lines) else ""
    return ExceptionTransparencyFinding(
        category=category,
        path=rel_path,
        line=handler.lineno,
        message=MESSAGE_BY_CATEGORY[category],
        snippet=snippet[:120],
    )


def comment_text(line: str) -> str | None:
    comment_index = line.find("#")
    if comment_index == -1:
        return None
    return line[comment_index + 1 :].strip()


def line_indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def has_quality_exception_waiver(lines: list[str], handler: ast.ExceptHandler) -> bool:
    if not (0 < handler.lineno <= len(lines)):
        return False

    handler_line = lines[handler.lineno - 1]
    same_line_explanation = explanation_for_quality_exception_step(
        comment_text(handler_line),
        step_slug=QUALITY_EXCEPTION_STEP_SLUG,
    )
    if same_line_explanation is not None:
        return bool(same_line_explanation)

    # Scan back through any run of consecutive comment lines at the handler's
    # indent level (up to 10 lines).  This allows multi-line quality-exception
    # explanations: the tag may appear on the first line of a block comment
    # whose last line sits immediately before the `except`.
    handler_indent = line_indent(handler_line)
    for look_back in range(1, 11):
        preceding_index = handler.lineno - 1 - look_back
        if preceding_index < 0:
            break
        preceding_line = lines[preceding_index]
        if not preceding_line.lstrip().startswith("#"):
            break
        if line_indent(preceding_line) != handler_indent:
            break
        explanation = explanation_for_quality_exception_step(
            comment_text(preceding_line),
            step_slug=QUALITY_EXCEPTION_STEP_SLUG,
        )
        if explanation is not None:
            return bool(explanation)
    return False


def scan_python_source(source: str, *, rel_path: str) -> list[ExceptionTransparencyFinding]:
    try:
        tree = ast.parse(source)
    except _PARSE_SKIP_EXCEPTIONS:
        return []

    lines = source.splitlines()
    findings: list[ExceptionTransparencyFinding] = []
    try_nodes: tuple[type[ast.AST], ...]
    try_star = getattr(ast, "TryStar", None)
    if try_star is not None:
        try_nodes = (ast.Try, try_star)
    else:
        try_nodes = (ast.Try,)

    for node in ast.walk(tree):
        if not isinstance(node, try_nodes):
            continue
        handlers = getattr(node, "handlers", [])
        for handler in handlers:
            if not isinstance(handler, ast.ExceptHandler) or not is_broad_handler(handler):
                continue
            if has_quality_exception_waiver(lines, handler):
                continue

            findings.append(make_finding("broad_except_total", rel_path, handler, lines))

            if handler.type is None:
                findings.append(make_finding("naked_except", rel_path, handler, lines))
            else:
                type_names = handler_type_names(handler.type)
                if "BaseException" in type_names:
                    findings.append(make_finding("baseexception_catch", rel_path, handler, lines))

            if contains_reraise(handler.body):
                continue
            if contains_traceback_logging(handler.body):
                findings.append(make_finding("broad_except_traceback_logged", rel_path, handler, lines))
            elif contains_signal(handler.body):
                findings.append(make_finding("broad_except_logged_no_traceback", rel_path, handler, lines))
            else:
                findings.append(make_finding("broad_except_unlogged", rel_path, handler, lines))

    return findings


def collect_findings(root: Path) -> list[ExceptionTransparencyFinding]:
    findings: list[ExceptionTransparencyFinding] = []
    for path in iter_python_files(root):
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except _SOURCE_READ_SKIP_EXCEPTIONS:
            continue
        rel_path = str(path.relative_to(root))
        findings.extend(scan_python_source(source, rel_path=rel_path))
    return findings


def count_broad_waivers(root: Path) -> int:
    """Count broad exception handlers with valid @quality-exception exception-transparency waivers."""
    total = 0
    for path in iter_python_files(root):
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (*_PARSE_SKIP_EXCEPTIONS, *_SOURCE_READ_SKIP_EXCEPTIONS):
            continue
        lines = source.splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Try):
                continue
            for handler in getattr(node, "handlers", []):
                if not isinstance(handler, ast.ExceptHandler) or not is_broad_handler(handler):
                    continue
                if has_quality_exception_waiver(lines, handler):
                    total += 1
    return total
