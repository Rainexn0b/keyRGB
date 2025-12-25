from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..utils.subproc import RunResult


@dataclass(frozen=True)
class Step:
    number: int
    name: str
    description: str
    log_file: Path
    runner: Callable[[], RunResult]


@dataclass(frozen=True)
class StepOutcome:
    status: str  # success|failure|skipped
    exit_code: int
    duration_s: float
    message: str = ""
