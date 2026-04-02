"""Exception transparency debt scan.

Tracks broad exception patterns that hide failures or make them harder to
diagnose in production. This step is report-only by default so the repo can
ratchet toward enforcement without breaking on the current backlog.
"""

from __future__ import annotations

import ast
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..utils.paths import repo_root
from ..utils.subproc import RunResult
from .quality_exceptions import explanation_for_quality_exception_step
from .reports import write_csv, write_json, write_md


_DEBT_BASELINE_PATH = Path("buildpython/config/debt_baselines.json")

_EXCLUDE_PATTERNS = [
    "vendor/",
    "__pycache__/",
    ".git/",
    "htmlcov/",
    "buildlog/",
    ".venv/",
]

_COUNT_CATEGORIES = [
    "naked_except",
    "baseexception_catch",
    "broad_except_total",
    "broad_except_traceback_logged",
    "broad_except_logged_no_traceback",
    "broad_except_unlogged",
]

_MESSAGE_BY_CATEGORY = {
    "naked_except": "Naked except catches KeyboardInterrupt/SystemExit; replace it with a specific exception type.",
    "baseexception_catch": "BaseException catch is too broad for normal control flow.",
    "broad_except_total": "Broad exception catch; prefer specific exception types where possible.",
    "broad_except_traceback_logged": "Broad exception catch records a traceback; still a narrowing candidate.",
    "broad_except_logged_no_traceback": "Broad exception catch signals failure without recording a traceback.",
    "broad_except_unlogged": "Broad exception catch suppresses failure without a diagnostic footprint.",
}

_TRACEBACK_SIGNAL_NAMES = {"log_exception", "_log_exception"}
_QUALITY_EXCEPTION_STEP_SLUG = "exception-transparency"
_SIGNAL_NAME_CALLS = {
    "print",
    "notify",
    "showerror",
    "showwarning",
    "showinfo",
    "log_throttled",
    "log_exception",
    "_log_exception",
}
_SIGNAL_ATTRS = {
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


@dataclass(frozen=True)
class ExceptionTransparencyFinding:
    category: str
    path: str
    line: int
    message: str
    snippet: str


@dataclass(frozen=True)
class ExceptionTransparencyBaseline:
    counts: dict[str, int]
    gated_categories: set[str]


def _should_exclude(path: Path, root: Path) -> bool:
    rel = str(path.relative_to(root))
    return any(pattern in rel for pattern in _EXCLUDE_PATTERNS)


def _iter_python_files(root: Path) -> Iterable[Path]:
    for folder in [root / "src", root / "buildpython"]:
        if not folder.exists():
            continue
        for path in folder.rglob("*.py"):
            if _should_exclude(path, root):
                continue
            yield path


def _load_baseline(root: Path) -> ExceptionTransparencyBaseline:
    config_path = root / _DEBT_BASELINE_PATH
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return ExceptionTransparencyBaseline(counts={}, gated_categories=set())

    section = payload.get("exception_transparency", {})
    counts_raw = section.get("counts", {})
    counts = {
        str(category): int(value)
        for category, value in counts_raw.items()
        if isinstance(category, str) and isinstance(value, int | float)
    }
    gated_categories = {
        str(category)
        for category in section.get("gated_categories", [])
        if isinstance(category, str)
    }
    return ExceptionTransparencyBaseline(counts=counts, gated_categories=gated_categories)


def _baseline_delta(current: int, baseline: int | None) -> str:
    if baseline is None:
        return "n/a"
    return f"{current - baseline:+d}"


def _baseline_regressions(
    counts: Counter[str],
    baseline: ExceptionTransparencyBaseline,
) -> list[tuple[str, int, int]]:
    regressions: list[tuple[str, int, int]] = []
    for category in sorted(baseline.gated_categories):
        current = counts.get(category, 0)
        expected = baseline.counts.get(category, 0)
        if current > expected:
            regressions.append((category, current, expected))
    return regressions


def _handler_type_names(node: ast.expr | None) -> set[str]:
    if node is None:
        return set()
    if isinstance(node, ast.Name):
        return {node.id}
    if isinstance(node, ast.Attribute):
        return {node.attr}
    if isinstance(node, ast.Tuple):
        names: set[str] = set()
        for element in node.elts:
            names.update(_handler_type_names(element))
        return names
    return set()


def _is_broad_handler(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    names = _handler_type_names(handler.type)
    return bool(names & {"Exception", "BaseException"})


def _contains_reraise(body: list[ast.stmt]) -> bool:
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Raise):
                return True
    return False


def _has_exc_info_keyword(call: ast.Call) -> bool:
    for keyword in call.keywords:
        if keyword.arg != "exc_info":
            continue
        value = keyword.value
        if isinstance(value, ast.Constant) and value.value is True:
            return True
        if isinstance(value, ast.NameConstant) and value.value is True:
            return True
    return False


def _has_named_exception_keyword(call: ast.Call, keyword_name: str) -> bool:
    for keyword in call.keywords:
        if keyword.arg != keyword_name:
            continue
        value = keyword.value
        if isinstance(value, ast.Constant):
            return value.value is not None
        return True
    return False


def _is_traceback_logging_call(call: ast.Call) -> bool:
    if isinstance(call.func, ast.Attribute):
        attr_name = call.func.attr.lower()
        if attr_name == "exception":
            return True
        if attr_name in {"error", "critical", "log"} and _has_exc_info_keyword(call):
            return True
        return attr_name in _TRACEBACK_SIGNAL_NAMES

    if isinstance(call.func, ast.Name):
        func_name = call.func.id.lower()
        if func_name == "log_throttled":
            return _has_named_exception_keyword(call, "exc")
        return func_name in _TRACEBACK_SIGNAL_NAMES

    return False


def _is_signal_call(call: ast.Call) -> bool:
    if _is_traceback_logging_call(call):
        return True

    if isinstance(call.func, ast.Attribute):
        return call.func.attr.lower() in _SIGNAL_ATTRS

    if isinstance(call.func, ast.Name):
        return call.func.id.lower() in _SIGNAL_NAME_CALLS

    return False


def _contains_traceback_logging(body: list[ast.stmt]) -> bool:
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and _is_traceback_logging_call(node):
                return True
    return False


def _contains_signal(body: list[ast.stmt]) -> bool:
    for stmt in body:
        for node in ast.walk(stmt):
            if isinstance(node, ast.Call) and _is_signal_call(node):
                return True
    return False


def _make_finding(category: str, rel_path: str, handler: ast.ExceptHandler, lines: list[str]) -> ExceptionTransparencyFinding:
    snippet = lines[handler.lineno - 1].strip() if 0 < handler.lineno <= len(lines) else ""
    return ExceptionTransparencyFinding(
        category=category,
        path=rel_path,
        line=handler.lineno,
        message=_MESSAGE_BY_CATEGORY[category],
        snippet=snippet[:120],
    )


def _comment_text(line: str) -> str | None:
    comment_index = line.find("#")
    if comment_index == -1:
        return None
    return line[comment_index + 1 :].strip()


def _line_indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


def _has_quality_exception_waiver(lines: list[str], handler: ast.ExceptHandler) -> bool:
    if not (0 < handler.lineno <= len(lines)):
        return False

    handler_line = lines[handler.lineno - 1]
    same_line_explanation = explanation_for_quality_exception_step(
        _comment_text(handler_line),
        step_slug=_QUALITY_EXCEPTION_STEP_SLUG,
    )
    if same_line_explanation is not None:
        return bool(same_line_explanation)

    previous_line_index = handler.lineno - 2
    if previous_line_index < 0:
        return False

    previous_line = lines[previous_line_index]
    if not previous_line.lstrip().startswith("#"):
        return False
    if _line_indent(previous_line) != _line_indent(handler_line):
        return False

    previous_line_explanation = explanation_for_quality_exception_step(
        _comment_text(previous_line),
        step_slug=_QUALITY_EXCEPTION_STEP_SLUG,
    )
    if previous_line_explanation is None:
        return False
    return bool(previous_line_explanation)


def _scan_python_source(source: str, *, rel_path: str) -> list[ExceptionTransparencyFinding]:
    try:
        tree = ast.parse(source)
    except Exception:
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
            if not isinstance(handler, ast.ExceptHandler) or not _is_broad_handler(handler):
                continue
            if _has_quality_exception_waiver(lines, handler):
                continue

            findings.append(_make_finding("broad_except_total", rel_path, handler, lines))

            if handler.type is None:
                findings.append(_make_finding("naked_except", rel_path, handler, lines))
            else:
                type_names = _handler_type_names(handler.type)
                if "BaseException" in type_names:
                    findings.append(_make_finding("baseexception_catch", rel_path, handler, lines))

            if _contains_reraise(handler.body):
                continue
            if _contains_traceback_logging(handler.body):
                findings.append(_make_finding("broad_except_traceback_logged", rel_path, handler, lines))
            elif _contains_signal(handler.body):
                findings.append(_make_finding("broad_except_logged_no_traceback", rel_path, handler, lines))
            else:
                findings.append(_make_finding("broad_except_unlogged", rel_path, handler, lines))

    return findings


def _collect_findings(root: Path) -> list[ExceptionTransparencyFinding]:
    findings: list[ExceptionTransparencyFinding] = []
    for path in _iter_python_files(root):
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel_path = str(path.relative_to(root))
        findings.extend(_scan_python_source(source, rel_path=rel_path))
    return findings


def _top_files_by_category(findings: list[ExceptionTransparencyFinding]) -> dict[str, list[tuple[str, int]]]:
    grouped: dict[str, Counter[str]] = {}
    for finding in findings:
        grouped.setdefault(finding.category, Counter())[finding.path] += 1
    return {
        category: counter.most_common(20)
        for category, counter in grouped.items()
    }


def _build_stdout(
    findings: list[ExceptionTransparencyFinding],
    counts: Counter[str],
    baseline: ExceptionTransparencyBaseline,
) -> list[str]:
    lines: list[str] = []
    top_files = _top_files_by_category(findings)
    regressions = _baseline_regressions(counts, baseline)

    lines.append("Exception Transparency Check")
    lines.append("=" * 40)
    lines.append("")
    lines.append("Policy: report-only for now; ratchet with baseline gating later.")
    lines.append("")
    lines.append("Counts:")
    for category in _COUNT_CATEGORIES:
        current = counts.get(category, 0)
        baseline_count = baseline.counts.get(category)
        baseline_text = "-" if baseline_count is None else str(baseline_count)
        delta = _baseline_delta(current, baseline_count)
        lines.append(f"  {category:<32} {current:>4} baseline={baseline_text:<4} delta={delta}")

    if regressions:
        lines.append("")
        lines.append("Regression-gated increases:")
        for category, current, expected in regressions:
            lines.append(f"  {category}: {current} > baseline {expected}")

    for category, title in [
        ("broad_except_unlogged", "Unlogged broad catch hotspots"),
        ("broad_except_logged_no_traceback", "Broad catch hotspots without traceback"),
        ("broad_except_total", "Broad catch hotspots"),
        ("naked_except", "Naked except hotspots"),
    ]:
        hotspots = top_files.get(category, [])
        if not hotspots:
            continue
        lines.append("")
        lines.append(f"{title}:")
        for path, count in hotspots[:10]:
            lines.append(f"  {count:>3}  {path}")

    if findings:
        lines.append("")
        lines.append("Sample findings (first 60):")
        for finding in findings[:60]:
            lines.append(f"  [{finding.category}] {finding.path}:{finding.line}")
            lines.append(f"    {finding.message}")
            if finding.snippet:
                lines.append(f"    > {finding.snippet}")

    return lines


def _write_reports(
    root: Path,
    findings: list[ExceptionTransparencyFinding],
    counts: Counter[str],
    baseline: ExceptionTransparencyBaseline,
) -> None:
    report_dir = root / "buildlog" / "keyrgb"
    report_dir.mkdir(parents=True, exist_ok=True)

    top_files = _top_files_by_category(findings)
    regressions = _baseline_regressions(counts, baseline)

    write_json(
        report_dir / "exception-transparency.json",
        {
            "counts": {category: int(counts.get(category, 0)) for category in _COUNT_CATEGORIES},
            "baseline": {
                "counts": baseline.counts,
                "gated_categories": sorted(baseline.gated_categories),
                "regressions": [
                    {"category": category, "current": current, "baseline": expected}
                    for category, current, expected in regressions
                ],
            },
            "top_files_by_category": {
                category: [{"path": path, "count": count} for path, count in file_counts]
                for category, file_counts in top_files.items()
            },
            "findings": [
                {
                    "category": finding.category,
                    "path": finding.path,
                    "line": finding.line,
                    "message": finding.message,
                    "snippet": finding.snippet,
                }
                for finding in findings[:500]
            ],
        },
    )

    write_csv(
        report_dir / "exception-transparency.csv",
        ["category", "path", "line", "message", "snippet"],
        [[finding.category, finding.path, str(finding.line), finding.message, finding.snippet] for finding in findings[:500]],
    )

    md_lines: list[str] = [
        "# Exception Transparency Report",
        "",
        "Report-only debt gate for broad exception handling. Counts are advisory until baseline gating is enabled.",
        "",
        "## Summary",
        "",
        "| Category | Count | Baseline | Delta |",
        "|----------|------:|---------:|------:|",
    ]
    for category in _COUNT_CATEGORIES:
        current = counts.get(category, 0)
        baseline_count = baseline.counts.get(category)
        baseline_text = "-" if baseline_count is None else str(baseline_count)
        delta = _baseline_delta(current, baseline_count)
        md_lines.append(f"| {category} | {current} | {baseline_text} | {delta} |")

    if regressions:
        md_lines.extend(["", "## Regression-Gated Increases", "", "| Category | Current | Baseline |", "|----------|--------:|---------:|"])
        for category, current, expected in regressions:
            md_lines.append(f"| {category} | {current} | {expected} |")

    for category, title in [
        ("broad_except_unlogged", "Unlogged Broad Catch Hotspots"),
        ("broad_except_logged_no_traceback", "Broad Catch Hotspots Without Traceback"),
        ("broad_except_total", "Broad Catch Hotspots"),
        ("naked_except", "Naked Except Hotspots"),
    ]:
        hotspots = top_files.get(category, [])
        if not hotspots:
            continue
        md_lines.extend(["", f"## {title}", "", "| File | Count |", "|------|------:|"])
        for path, count in hotspots[:15]:
            md_lines.append(f"| {path} | {count} |")

    if findings:
        md_lines.extend(["", "## Findings (sample)", ""])
        for finding in findings[:100]:
            md_lines.append(f"### `{finding.category}` at {finding.path}:{finding.line}")
            md_lines.append("")
            md_lines.append(f"**{finding.message}**")
            if finding.snippet:
                md_lines.extend(["```python", finding.snippet, "```"])
            md_lines.append("")

    write_md(report_dir / "exception-transparency.md", md_lines)


def exception_transparency_runner() -> RunResult:
    root = repo_root()
    findings = _collect_findings(root)
    baseline = _load_baseline(root)

    counts: Counter[str] = Counter()
    for finding in findings:
        counts[finding.category] += 1

    stdout_lines = _build_stdout(findings, counts, baseline)
    _write_reports(root, findings, counts, baseline)

    should_fail = bool(_baseline_regressions(counts, baseline))
    exit_code = 1 if should_fail else 0
    return RunResult(
        command_str="(internal) exception transparency check",
        stdout="\n".join(stdout_lines) + "\n",
        stderr="",
        exit_code=exit_code,
    )