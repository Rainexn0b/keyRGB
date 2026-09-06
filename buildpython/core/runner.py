from __future__ import annotations

import importlib.util
import shutil
import time

from ..utils.paths import buildlog_dir
from . import summary as summary_module
from .debt_index import write_debt_index
from .model import Step, StepOutcome
from .runner_support import display as _ui


def _is_module_available(module: str) -> bool:
    return importlib.util.find_spec(module) is not None


def run_step(
    step: Step, *, index: int, total_steps: int, name_width: int, label_width: int, verbose: bool
) -> StepOutcome:
    start = time.time()
    _ui._print_step_header(step, index=index, total_steps=total_steps, name_width=name_width, label_width=label_width)

    # Optional step gating
    if step.name in {"Ruff", "Ruff Format"} and not _is_module_available("ruff"):
        duration = time.time() - start
        _ui._write_log(
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
        _ui._print_step_footer(outcome, ["ruff not installed"])
        return outcome

    if step.name == "Black" and not _is_module_available("black"):
        duration = time.time() - start
        _ui._write_log(
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
        _ui._print_step_footer(outcome, ["black not installed"])
        return outcome

    if step.name == "Type Check" and not _is_module_available("mypy"):
        duration = time.time() - start
        _ui._write_log(
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
        _ui._print_step_footer(outcome, ["mypy not installed"])
        return outcome

    if step.name == "Coverage" and (not _is_module_available("coverage") or not _is_module_available("pytest")):
        duration = time.time() - start
        _ui._write_log(
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
        _ui._print_step_footer(outcome, ["coverage or pytest not installed"])
        return outcome

    if step.name == "Dead Code" and not _is_module_available("vulture"):
        duration = time.time() - start
        _ui._write_log(
            step,
            "python -m vulture ...",
            "(skipped: vulture not installed)\n",
            "",
            0,
            duration,
        )
        outcome = StepOutcome(
            status="skipped",
            exit_code=0,
            duration_s=duration,
            message="vulture not installed",
        )
        _ui._print_step_footer(outcome, ["vulture not installed"])
        return outcome

    if step.name == "ShellCheck" and shutil.which("shellcheck") is None:
        duration = time.time() - start
        _ui._write_log(
            step,
            "shellcheck ...",
            "(skipped: shellcheck not installed)\n",
            "",
            0,
            duration,
        )
        outcome = StepOutcome(
            status="skipped",
            exit_code=0,
            duration_s=duration,
            message="shellcheck not installed",
        )
        _ui._print_step_footer(outcome, ["shellcheck not installed"])
        return outcome

    result = step.runner()
    duration = time.time() - start

    _ui._write_log(
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
    highlights = _ui._step_highlights(step, stdout=result.stdout, stderr=result.stderr)
    _ui._print_step_footer(outcome, highlights)

    if verbose or result.exit_code != 0:
        if result.stdout.strip():
            print(result.stdout.rstrip())
        if result.stderr.strip():
            print(result.stderr.rstrip())

    return outcome


def _completed_run_exit_code(summaries: list[summary_module.StepSummary]) -> int:
    """Return the first failed step's code after every selected step ran."""

    for step in summaries:
        if step.status == "failure":
            # A failure status should always carry a nonzero subprocess code,
            # but retain a safe shell failure if a custom step violates that
            # invariant.
            return step.exit_code if step.exit_code != 0 else 1
    return 0


def run(steps: list[Step], *, verbose: bool, continue_on_error: bool) -> int:
    total_steps = len(steps)
    name_width = max((len(step.name) for step in steps), default=7)
    label_width = len(f"[{total_steps}/{total_steps}]")
    build_label = f"\u00b7  {total_steps} steps  \u00b7  Logs in {buildlog_dir()}"

    print(f"\U0001f527  {_ui._color('KeyRGB Build', _ui._BOLD + _ui._CYAN)}  {_ui._color(build_label, _ui._DIM)}")

    started = time.time()
    summaries: list[summary_module.StepSummary] = []

    def _health_score() -> int:
        considered = [s for s in summaries if s.status != "skipped"]
        if not considered:
            return 100
        successes = sum(1 for s in considered if s.status == "success")
        return round(100 * successes / len(considered))

    for index, step in enumerate(steps, start=1):
        outcome = run_step(
            step, index=index, total_steps=total_steps, name_width=name_width, label_width=label_width, verbose=verbose
        )

        summaries.append(
            summary_module.StepSummary(
                number=step.number,
                name=step.name,
                status=outcome.status,
                exit_code=outcome.exit_code,
                duration_s=outcome.duration_s,
            )
        )

        if outcome.status == "failure" and not continue_on_error:
            print(f"\n{_ui._status_icon('failure')}Build stopped at [{index}/{total_steps}]: {step.name}")

            score = _health_score()

            summary_module.write_summary(
                buildlog_dir(),
                summary_module.BuildSummary(
                    passed=False,
                    health_score=score,
                    total_duration_s=time.time() - started,
                    steps=summaries,
                ),
            )
            write_debt_index(buildlog_dir())

            final_summary = summary_module.BuildSummary(
                passed=False,
                health_score=score,
                total_duration_s=time.time() - started,
                steps=summaries,
            )
            for line in summary_module.build_terminal_build_overview(buildlog_dir(), final_summary):
                print(line)

            return outcome.exit_code

    final_exit_code = _completed_run_exit_code(summaries)
    passed = final_exit_code == 0
    score = _health_score()

    summary_module.write_summary(
        buildlog_dir(),
        summary_module.BuildSummary(
            passed=passed,
            health_score=score,
            total_duration_s=time.time() - started,
            steps=summaries,
        ),
    )
    write_debt_index(buildlog_dir())

    final_summary = summary_module.BuildSummary(
        passed=passed,
        health_score=score,
        total_duration_s=time.time() - started,
        steps=summaries,
    )
    for line in summary_module.build_terminal_build_overview(buildlog_dir(), final_summary):
        print(line)

    return final_exit_code
