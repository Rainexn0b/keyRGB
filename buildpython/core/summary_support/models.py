from __future__ import annotations

from dataclasses import dataclass

from ..model import StepHealth


@dataclass(frozen=True)
class StepSummary:
    number: int
    name: str
    status: str  # success|failure|skipped|not_run|running (incomplete run)
    exit_code: int | None
    duration_s: float
    message: str = ""
    log_file: str = ""
    health: StepHealth | None = None


@dataclass(frozen=True)
class BuildSummary:
    total_duration_s: float
    steps: list[StepSummary]
    run_id: str = ""
    started_at: str = ""
    report_names: tuple[str, ...] = ()
    completed: bool = True

    @property
    def counts(self) -> dict[str, int]:
        return {
            status: sum(step.status == status for step in self.steps)
            for status in ("success", "failure", "skipped", "not_run", "running")
        }

    @property
    def status(self) -> str:
        if not self.completed:
            return "incomplete"
        counts = self.counts
        if counts["failure"]:
            return "failed"
        if not counts["success"]:
            return "not_run"
        if counts["skipped"] or counts["not_run"]:
            return "partial"
        return "passed"

    @property
    def passed(self) -> bool:
        return self.status == "passed"

    @property
    def exit_code(self) -> int | None:
        if not self.completed:
            return None
        return next((step.exit_code or 1 for step in self.steps if step.status == "failure"), 0)
