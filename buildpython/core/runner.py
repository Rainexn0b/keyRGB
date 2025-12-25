from __future__ import annotations

import time
from pathlib import Path

from .model import Step, StepOutcome
from .summary import BuildSummary, StepSummary, write_summary
from ..utils.log_format import StepLogRecord, format_standard_log
from ..utils.paths import buildlog_dir


def _write_log(step: Step, command: str, stdout: str, stderr: str, exit_code: int, duration_s: float) -> None:
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


def run_step(step: Step, *, verbose: bool) -> StepOutcome:
    start = time.time()

    # Optional step gating
    if step.name in {"Ruff", "Ruff Format"} and not _is_module_available("ruff"):
        duration = time.time() - start
        _write_log(step, "python -m ruff ...", "(skipped: ruff not installed)\n", "", 0, duration)
        print(f"[{step.number}] {step.name}: SKIPPED")
        return StepOutcome(status="skipped", exit_code=0, duration_s=duration, message="ruff not installed")

    result = step.runner()
    duration = time.time() - start

    _write_log(step, result.command_str, result.stdout, result.stderr, result.exit_code, duration)

    status = "OK" if result.exit_code == 0 else "FAIL"
    print(f"[{step.number}] {step.name}: {status} ({duration:.1f}s)")

    if verbose or result.exit_code != 0:
        if result.stdout.strip():
            print(result.stdout.rstrip())
        if result.stderr.strip():
            print(result.stderr.rstrip())

    return StepOutcome(
        status="success" if result.exit_code == 0 else "failure",
        exit_code=result.exit_code,
        duration_s=duration,
    )


def run(steps: list[Step], *, verbose: bool, continue_on_error: bool) -> int:
    print(f"KeyRGB build runner (logs: {buildlog_dir()})")

    started = time.time()
    summaries: list[StepSummary] = []

    def _health_score() -> int:
        considered = [s for s in summaries if s.status != "skipped"]
        if not considered:
            return 100
        successes = sum(1 for s in considered if s.status == "success")
        return int(round(100 * successes / len(considered)))

    def _print_health(score: int) -> None:
        bar_width = 20
        filled = max(0, min(bar_width, int(round(score / 100 * bar_width))))
        bar = "[" + ("#" * filled) + ("-" * (bar_width - filled)) + "]"
        print(f"Build health: {score}/100 {bar}")

    for step in steps:
        outcome = run_step(step, verbose=verbose)

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

            _print_health(score)

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

    _print_health(score)

    return 0
