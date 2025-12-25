from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class StepLogRecord:
    step_name: str
    command: str
    duration_s: float
    exit_code: int
    stdout: str
    stderr: str


def format_standard_log(record: StepLogRecord) -> str:
    duration_text = f"({record.duration_s:.1f}s)"
    stdout = record.stdout if record.stdout.strip() else "(no stdout)"
    stderr = record.stderr if record.stderr.strip() else "(no stderr)"

    return (
        f"=== {record.step_name} - {iso_now()} ===\n"
        f"Command: {record.command}\n"
        f"Duration: {duration_text}\n"
        f"Exit Code: {record.exit_code}\n\n"
        f"=== STDOUT ===\n{stdout}\n\n"
        f"=== STDERR ===\n{stderr}\n\n"
        f"=== END ===\n"
    )
