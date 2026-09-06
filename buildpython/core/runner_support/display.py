from __future__ import annotations

import re
import sys

from ...utils.log_format import StepLogRecord, format_standard_log
from ...utils.paths import buildlog_dir
from .. import summary as summary_module
from ..model import Step, StepOutcome
from ..summary_support import debt_terminal

_USE_COLOR = sys.stdout.isatty()
_RESET = "\033[0m" if _USE_COLOR else ""
_BOLD = "\033[1m" if _USE_COLOR else ""
_DIM = "\033[2m" if _USE_COLOR else ""
_CYAN = "\033[36m" if _USE_COLOR else ""

_SEP = "\u2500" * 60  # ─────────────────────────────────────────────────────────────


def _color(text: str, code: str) -> str:
    if not code:
        return text
    return f"{code}{text}{_RESET}"


def _status_icon(status: str) -> str:
    """Fixed-width status prefix. Emoji glyphs are 2 terminal columns wide."""
    if status == "running":
        return "\u23f3  "  # ⏳
    if status == "success":
        return "\u2705  "  # ✅
    if status == "failure":
        return "\u274c  "  # ❌
    if status == "skipped":
        return "\u23ed\ufe0f  "  # ⏭️
    return "     "


def _print_step_header(step: Step, *, index: int, total_steps: int, name_width: int, label_width: int) -> None:
    print(_color(_SEP, _DIM))
    label = f"[{index}/{total_steps}]".ljust(label_width)
    name = f"{step.name:<{name_width}}"
    print(f"{_status_icon('running')}{label}  {name} : {step.description}", flush=True)


def _print_step_footer(outcome: StepOutcome, highlights: list[str]) -> None:
    icon = _status_icon(outcome.status)
    if outcome.status == "success":
        print(f"{icon}Completed ({outcome.duration_s:.1f}s)")
    elif outcome.status == "skipped":
        print(f"{icon}Skipped ({outcome.duration_s:.1f}s)")
    else:
        print(f"{icon}Failed ({outcome.duration_s:.1f}s)")

    for line in highlights:
        print(f"    {line}")


def _extract_pytest_highlight(stdout: str, stderr: str) -> str | None:
    text = f"{stdout}\n{stderr}"
    patterns = [
        r"(\d+ passed(?:, \d+ skipped)?(?:, \d+ deselected)?(?:, \d+ xfailed)?(?:, \d+ xpassed)?(?:, \d+ warnings?)?) in [^\n]+",
        r"(\d+ failed(?:, \d+ passed)?(?:, \d+ skipped)?(?:, \d+ errors?)?) in [^\n]+",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            return f"Tests: {matches[-1]}"
    return None


def _step_highlights(step: Step, *, stdout: str, stderr: str) -> list[str]:
    highlights: list[str] = []
    if step.name == "Pytest":
        pytest_line = _extract_pytest_highlight(stdout, stderr)
        if pytest_line is not None:
            highlights.append(pytest_line)
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
    exit_code: int,
    duration_s: float,
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
    )
    step.log_file.write_text(format_standard_log(record), encoding="utf-8")
