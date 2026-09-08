from __future__ import annotations

import re
import sys

from ...utils.log_format import StepLogRecord, format_standard_log
from ...utils.paths import buildlog_dir
from .. import summary as summary_module
from ..model import Step, StepOutcome
from ..summary_support import debt_terminal
from ..summary_support.common import read_json_if_exists
from .reports import STEP_REPORTS

_USE_COLOR = sys.stdout.isatty()
_RESET = "\033[0m" if _USE_COLOR else ""
_BOLD = "\033[1m" if _USE_COLOR else ""
_DIM = "\033[2m" if _USE_COLOR else ""
_CYAN = "\033[36m" if _USE_COLOR else ""
_BLUE = "\033[34m" if _USE_COLOR else ""
_GREEN = "\033[32m" if _USE_COLOR else ""
_YELLOW = "\033[33m" if _USE_COLOR else ""
_RED = "\033[31m" if _USE_COLOR else ""

_SEP = "\u2500" * 60  # ─────────────────────────────────────────────────────────────


def _color(text: str, code: str) -> str:
    if not code:
        return text
    return f"{code}{text}{_RESET}"


def _status_icon(status: str) -> str:
    """Fixed-width status prefix. Emoji glyphs are 2 terminal columns wide."""
    if status == "running":
        return "\U0001f504  "  # 🔄
    if status == "success":
        return "\u2705  "  # ✅
    if status == "failure":
        return "\u274c  "  # ❌
    if status == "skipped":
        return "\u2757  "  # ❗
    return "     "


def _status_color(status: str) -> str:
    if status == "running":
        return _BLUE
    if status == "success":
        return _GREEN
    if status == "failure":
        return _RED
    if status == "skipped":
        return _YELLOW
    return ""


def _print_step_header(step: Step, *, index: int, total_steps: int, name_width: int, label_width: int) -> None:
    print(_color(_SEP, _DIM))
    label = f"[{index}/{total_steps}]".ljust(label_width)
    name = f"{step.name:<{name_width}}"
    print(
        _color(f"{_status_icon('running')}{label}  {name} : {step.description}", _status_color("running")),
        flush=True,
    )


def _print_step_footer(outcome: StepOutcome, highlights: list[str]) -> None:
    icon = _status_icon(outcome.status)
    if outcome.status == "success":
        text = f"{icon}Completed ({outcome.duration_s:.1f}s)"
    elif outcome.status == "skipped":
        text = f"{icon}Skipped ({outcome.duration_s:.1f}s)"
    else:
        text = f"{icon}Failed ({outcome.duration_s:.1f}s)"
    print(_color(text, _status_color(outcome.status)))

    if outcome.health is not None:
        health = outcome.health
        filled = int(health.score / 5)
        bar = "█" * filled + "░" * (20 - filled)
        print(f"    {health.label}: [{bar}] {health.score:g}% (penalty score)")

    for line in highlights:
        print(_color(f"    {line}", _DIM))


def _print_compact_step_footer(outcome: StepOutcome) -> None:
    _print_step_footer(outcome, list(outcome.highlights))


def _print_failure_guidance(step: Step, *, index: int, total_steps: int) -> None:
    print()
    print(_color(f"{_status_icon('failure')}Build stopped at [{index}/{total_steps}]: {step.name}", _RED))
    print(_color(f"→ See {step.log_file}", _YELLOW))


def _extract_pytest_highlight(stdout: str, stderr: str) -> str | None:
    for line in reversed(f"{stdout}\n{stderr}".splitlines()):
        if not re.search(r"\bin \d+(?:\.\d+)?s\b", line):
            continue
        counts = re.findall(
            r"\b\d+ (?:passed|failed|skipped|deselected|xfailed|xpassed|errors?|warnings?|rerun)\b", line
        )
        if counts:
            return "Tests: " + ", ".join(counts)
    return None


def _extract_import_scan_highlight(stdout: str) -> str | None:
    section: str | None = None
    required: list[str] = []
    optional: list[str] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if line == "Missing required imports:":
            section = "required"
            continue
        if line == "Missing optional imports:":
            section = "optional"
            continue
        if line.endswith(":") or not line:
            section = None
            continue
        if not line.startswith("- ") or section is None:
            continue
        module = line[2:].split(" ", 1)[0]
        (required if section == "required" else optional).append(module)
    if required:
        return f"Missing required imports: {', '.join(required)}"
    if optional:
        return f"Optional imports unavailable: {', '.join(optional)}"
    return None


def _step_highlights(step: Step, *, stdout: str, stderr: str, report_names: tuple[str, ...] = ()) -> list[str]:
    highlights: list[str] = []
    report_name = STEP_REPORTS.get(step.name)
    if report_name is not None and report_name not in report_names:
        return ["No report produced by this invocation; see the step log."]
    if step.name in {"Architecture Validation", "Dead Code"}:
        report = read_json_if_exists(buildlog_dir() / str(report_name))
        if report is None:
            return ["Report unreadable; see the step log."]
        if step.name == "Architecture Validation":
            counts = report.get("summary", {})
            return [
                (
                    f"Rules checked: {counts.get('rules_checked', 'unknown')} | "
                    f"Files scanned: {counts.get('scanned_files', 'unknown')} | "
                    f"Errors: {counts.get('errors', 'unknown')} | Warnings: {counts.get('warnings', 'unknown')}"
                )
            ]
        return [
            f"Unused-code candidates: {report.get('count', 'unknown')} | Actionable: {report.get('actionable_count', 'unknown')}"
        ]
    if step.name == "Pytest":
        pytest_line = _extract_pytest_highlight(stdout, stderr)
        if pytest_line is not None:
            highlights.append(pytest_line)
    elif step.name == "Import Validation":
        highlights.extend(
            line.strip()
            for line in stdout.splitlines()
            if line.startswith(("Checked imports:", "Skipped GUI imports:"))
        )
    elif step.name == "AppImage":
        highlights.extend(
            line
            for line in stdout.splitlines()
            if line.startswith(("Built AppImage:", "Runtime dependency installation skipped"))
        )
    elif step.name == "Repo Validation":
        if "Warnings:" in stdout:
            highlights.append("Repository warnings reported; see the step log.")
    elif step.name == "Import Scan":
        import_line = _extract_import_scan_highlight(stdout)
        if import_line is not None:
            highlights.append(import_line)
    elif step.name == "Code Markers":
        highlights.extend(debt_terminal.build_terminal_markers_highlight(buildlog_dir()))
    elif step.name == "File Size":
        highlights.extend(debt_terminal.build_terminal_filesize_highlight(buildlog_dir()))
    elif step.name == "LOC Check":
        highlights.extend(debt_terminal.build_terminal_loc_check_highlight(buildlog_dir()))
    elif step.name == "Coverage":
        coverage_line = summary_module.build_terminal_coverage_highlight(buildlog_dir())
        if coverage_line is not None:
            highlights.append(coverage_line)
    elif step.name == "Code Hygiene":
        highlights.extend(debt_terminal.build_terminal_hygiene_highlight(buildlog_dir()))
    elif step.name == "Exception Transparency":
        highlights.extend(debt_terminal.build_terminal_transparency_highlight(buildlog_dir()))
    return highlights


def _write_log(
    step: Step,
    command: str,
    stdout: str,
    stderr: str,
    exit_code: int | None,
    duration_s: float,
    *,
    status: str = "",
) -> None:
    buildlog_dir().mkdir(parents=True, exist_ok=True)
    step.log_file.parent.mkdir(parents=True, exist_ok=True)

    record = StepLogRecord(
        step_name=step.name,
        command=command,
        duration_s=duration_s,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        status=status,
    )
    step.log_file.write_text(format_standard_log(record), encoding="utf-8")
