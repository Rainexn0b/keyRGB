from __future__ import annotations

import time
from pathlib import Path

from .model import Step, StepOutcome
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
    if step.name == "Ruff" and not _is_module_available("ruff"):
        duration = time.time() - start
        _write_log(step, "python -m ruff check src", "(skipped: ruff not installed)\n", "", 0, duration)
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

    for step in steps:
        outcome = run_step(step, verbose=verbose)
        if outcome.status == "failure" and not continue_on_error:
            print(f"Stopped on failure in step {step.number}: {step.name}")
            return outcome.exit_code

    return 0
