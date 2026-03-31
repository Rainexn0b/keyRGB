from __future__ import annotations

import re
import sys
import time

from .debt_index import write_debt_index
from .model import Step, StepOutcome
from .summary import (
    BuildSummary,
    StepSummary,
    build_terminal_build_overview,
    build_terminal_coverage_highlight,
    build_terminal_debt_snapshot,
    write_summary,
)
from ..utils.log_format import StepLogRecord, format_standard_log
from ..utils.paths import buildlog_dir


_USE_COLOR = sys.stdout.isatty()
_RESET = "\033[0m" if _USE_COLOR else ""
_BOLD = "\033[1m" if _USE_COLOR else ""
_DIM = "\033[2m" if _USE_COLOR else ""
_RED = "\033[31m" if _USE_COLOR else ""
_GREEN = "\033[32m" if _USE_COLOR else ""
_YELLOW = "\033[33m" if _USE_COLOR else ""
_BLUE = "\033[34m" if _USE_COLOR else ""
_CYAN = "\033[36m" if _USE_COLOR else ""


def _color(text: str, code: str) -> str:
    if not code:
        return text
    return f"{code}{text}{_RESET}"


def _status_badge(status: str) -> str:
    if status == "running":
        return _color("[..]", _CYAN)
    if status == "success":
        return _color("[OK]", _GREEN)
    if status == "failure":
        return _color("[!!]", _RED)
    if status == "skipped":
        return _color("[--]", _YELLOW)
    return "[??]"


def _print_step_header(step: Step, *, index: int, total_steps: int, name_width: int) -> None:
    print(_color("-" * 72, _DIM))
    step_label = f"[{index}/{total_steps}]"
    name = f"{step.name:<{name_width}}"
    print(f"{_status_badge('running')} {step_label} {name} : {step.description}")


def _print_step_footer(outcome: StepOutcome, highlights: list[str]) -> None:
    if outcome.status == "success":
        print(f"Completed ({outcome.duration_s:.1f}s)")
    elif outcome.status == "skipped":
        print(f"Skipped ({outcome.duration_s:.1f}s)")
    else:
        print(f"Failed ({outcome.duration_s:.1f}s)")

    for line in highlights:
        print(f"  {line}")


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
    if step.name == "Coverage":
        coverage_line = build_terminal_coverage_highlight(buildlog_dir())
        if coverage_line is not None:
            highlights.append(coverage_line)
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


def _is_module_available(module: str) -> bool:
    try:
        __import__(module)
        return True
    except Exception:
        return False


def run_step(step: Step, *, index: int, total_steps: int, name_width: int, verbose: bool) -> StepOutcome:
    start = time.time()
    _print_step_header(step, index=index, total_steps=total_steps, name_width=name_width)

    # Optional step gating
    if step.name in {"Ruff", "Ruff Format"} and not _is_module_available("ruff"):
        duration = time.time() - start
        _write_log(
            step,
            "python -m ruff ...",
            "(skipped: ruff not installed)\n",
            "",
            0,
            duration,
        )
        outcome = StepOutcome(
            status="skipped",
            exit_code=0,
            duration_s=duration,
            message="ruff not installed",
        )
        _print_step_footer(outcome, ["ruff not installed"])
        return outcome

    if step.name == "Black" and not _is_module_available("black"):
        duration = time.time() - start
        _write_log(
            step,
            "python -m black ...",
            "(skipped: black not installed)\n",
            "",
            0,
            duration,
        )
        outcome = StepOutcome(
            status="skipped",
            exit_code=0,
            duration_s=duration,
            message="black not installed",
        )
        _print_step_footer(outcome, ["black not installed"])
        return outcome

    if step.name == "Type Check" and not _is_module_available("mypy"):
        duration = time.time() - start
        _write_log(
            step,
            "python -m mypy ...",
            "(skipped: mypy not installed)\n",
            "",
            0,
            duration,
        )
        outcome = StepOutcome(
            status="skipped",
            exit_code=0,
            duration_s=duration,
            message="mypy not installed",
        )
        _print_step_footer(outcome, ["mypy not installed"])
        return outcome

    if step.name == "Coverage" and (not _is_module_available("coverage") or not _is_module_available("pytest")):
        duration = time.time() - start
        _write_log(
            step,
            "python -m coverage ...",
            "(skipped: coverage or pytest not installed)\n",
            "",
            0,
            duration,
        )
        outcome = StepOutcome(
            status="skipped",
            exit_code=0,
            duration_s=duration,
            message="coverage or pytest not installed",
        )
        _print_step_footer(outcome, ["coverage or pytest not installed"])
        return outcome

    result = step.runner()
    duration = time.time() - start

    _write_log(
        step,
        result.command_str,
        result.stdout,
        result.stderr,
        result.exit_code,
        duration,
    )

    outcome = StepOutcome(
        status="success" if result.exit_code == 0 else "failure",
        exit_code=result.exit_code,
        duration_s=duration,
    )
    highlights = _step_highlights(step, stdout=result.stdout, stderr=result.stderr)
    _print_step_footer(outcome, highlights)

    if verbose or result.exit_code != 0:
        if result.stdout.strip():
            print(result.stdout.rstrip())
        if result.stderr.strip():
            print(result.stderr.rstrip())

    return outcome


def run(steps: list[Step], *, verbose: bool, continue_on_error: bool) -> int:
    total_steps = len(steps)
    name_width = max((len(step.name) for step in steps), default=7)

    print(_color("KeyRGB build runner", _BOLD + _CYAN))
    print(f"Logs: {buildlog_dir()}")
    print(f"Steps: {total_steps}")

    started = time.time()
    summaries: list[StepSummary] = []

    def _health_score() -> int:
        considered = [s for s in summaries if s.status != "skipped"]
        if not considered:
            return 100
        successes = sum(1 for s in considered if s.status == "success")
        return int(round(100 * successes / len(considered)))

    for index, step in enumerate(steps, start=1):
        outcome = run_step(step, index=index, total_steps=total_steps, name_width=name_width, verbose=verbose)

        summaries.append(
            StepSummary(
                number=step.number,
                name=step.name,
                status=outcome.status,
                exit_code=outcome.exit_code,
                duration_s=outcome.duration_s,
            )
        )

        if outcome.status == "failure" and not continue_on_error:
            print(f"Stopped on failure in step {step.number}: {step.name}")

            score = _health_score()

            write_summary(
                buildlog_dir(),
                BuildSummary(
                    passed=False,
                    health_score=score,
                    total_duration_s=time.time() - started,
                    steps=summaries,
                ),
            )
            write_debt_index(buildlog_dir())

            print(_color("-" * 72, _DIM))
            final_summary = BuildSummary(
                passed=False,
                health_score=score,
                total_duration_s=time.time() - started,
                steps=summaries,
            )
            for line in build_terminal_build_overview(buildlog_dir(), final_summary):
                print(line)
            for line in build_terminal_debt_snapshot(buildlog_dir(), include_coverage=False):
                print(line)

            return outcome.exit_code

    passed = all(s.status != "failure" for s in summaries)
    score = _health_score()

    write_summary(
        buildlog_dir(),
        BuildSummary(
            passed=passed,
            health_score=score,
            total_duration_s=time.time() - started,
            steps=summaries,
        ),
    )
    write_debt_index(buildlog_dir())

    print(_color("-" * 72, _DIM))
    final_summary = BuildSummary(
        passed=passed,
        health_score=score,
        total_duration_s=time.time() - started,
        steps=summaries,
    )
    for line in build_terminal_build_overview(buildlog_dir(), final_summary):
        print(line)
    for line in build_terminal_debt_snapshot(buildlog_dir(), include_coverage=False):
        print(line)

    return 0
