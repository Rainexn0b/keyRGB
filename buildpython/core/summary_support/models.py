from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StepSummary:
    number: int
    name: str
    status: str  # success|failure|skipped
    exit_code: int
    duration_s: float


@dataclass(frozen=True)
class BuildSummary:
    passed: bool
    health_score: int  # 0-100
    total_duration_s: float
    steps: list[StepSummary]
