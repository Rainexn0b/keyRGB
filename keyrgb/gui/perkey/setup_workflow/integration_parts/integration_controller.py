"""UX-04 guided setup integration: Tk-free guided setup controller.

Navigation state for the modal wizard. Back/Next only move ``step_index``
and mutate the in-memory draft; only :meth:`GuidedSetupController.finish`
reaches the commit boundary, and cancellation drops the draft with no
writes at all. A running calibrator child blocks nav/Finish/close (the
child process is never terminated).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..model import KeymapValidation, SetupDraft
from ..preflight import CalibrationPreflightResult, PreflightMode
from ..transaction import FinishResult, SetupCommitCallbacks, finish_setup
from .integration_preflight import calibration_skip_validation
from .integration_types import _EXPECTED_SESSION_ERRORS, SETUP_STEPS, SetupStep


@dataclass
class GuidedSetupController:
    """Tk-free guided setup flow state; navigation never persists.

    The wizard renders from this controller. Back/Next only move
    ``step_index`` and mutate the in-memory draft; only :meth:`finish`
    reaches the commit boundary, and cancellation drops the draft with no
    writes at all.
    """

    draft: SetupDraft
    preflight: CalibrationPreflightResult
    rows: int
    cols: int
    include_overlay: bool = True
    step_index: int = 0
    child_running: bool = False
    session_path: Path | None = None
    last_message: str = ""

    @property
    def steps(self) -> tuple[SetupStep, ...]:
        if self.include_overlay:
            return SETUP_STEPS
        return tuple(step for step in SETUP_STEPS if step is not SetupStep.OVERLAY)

    @property
    def current_step(self) -> SetupStep:
        steps = self.steps
        return steps[max(0, min(self.step_index, len(steps) - 1))]

    @property
    def config_only(self) -> bool:
        return self.preflight.mode is PreflightMode.CONFIG_ONLY

    @property
    def live(self) -> bool:
        return self.preflight.mode is PreflightMode.LIVE_PREVIEW

    @property
    def blocked(self) -> bool:
        return self.preflight.mode is PreflightMode.BLOCKED

    def keymap_validation(self) -> KeymapValidation:
        return calibration_skip_validation(self.draft.keymap, rows=self.rows, cols=self.cols)

    def may_skip_calibration(self) -> bool:
        return bool(self.keymap_validation().valid)

    def can_advance(self) -> tuple[bool, str]:
        """Return whether Next/Finish-navigation may leave the current step."""

        if self.child_running:
            return False, "The guided calibrator is still running; wait for it to close."
        step = self.current_step
        if step is SetupStep.PREFLIGHT and self.blocked:
            return False, self.preflight.message
        if step is SetupStep.CALIBRATION:
            validation = self.keymap_validation()
            if validation.valid:
                return True, ""
            if self.config_only:
                return (
                    False,
                    (
                        "The existing keymap is invalid and live key flashing is unavailable "
                        "and unverified in config-only mode. Retry with the keyboard connected, "
                        "or run live calibration, before continuing."
                    ),
                )
            return (
                False,
                f"The keymap is not ready ({validation.reason}); run guided calibration first.",
            )
        return True, ""

    def go_next(self) -> bool:
        """Advance one step without persisting; False with a message when gated."""

        allowed, message = self.can_advance()
        if not allowed:
            self.last_message = message
            return False
        if self.step_index < len(self.steps) - 1:
            self.step_index += 1
        self.last_message = ""
        return True

    def go_back(self) -> bool:
        """Move back one step without persisting; False while a child runs."""

        if self.child_running:
            self.last_message = "The guided calibrator is still running; wait for it to close."
            return False
        if self.step_index > 0:
            self.step_index -= 1
        self.last_message = ""
        return True

    def can_launch_calibrator(self) -> tuple[bool, str]:
        """Return whether a guided calibrator child may be launched now."""

        if self.child_running:
            return False, "The guided calibrator is already running."
        if self.blocked:
            return False, self.preflight.message
        if not self.live:
            return (
                False,
                "Live key flashing is unavailable in config-only mode; use a valid existing keymap or Retry.",
            )
        if self.preflight.reason.name == "ALREADY_RUNNING":
            return False, "Another calibration session is already running; a second calibrator cannot be launched."
        return True, ""

    def note_child_started(self, session_path: str | Path) -> None:
        """Record a running calibrator child (blocks nav/Finish/close)."""

        try:
            self.session_path = Path(session_path).expanduser()
        except _EXPECTED_SESSION_ERRORS:
            self.session_path = None
        self.child_running = True
        self.last_message = ""

    def note_child_finished(self) -> None:
        """Clear the running-child flag (temp cleanup stays with the wizard)."""

        self.child_running = False
        self.session_path = None
        self.last_message = ""

    def close_allowed(self) -> tuple[bool, str]:
        """Return whether Cancel/close may proceed (never terminates a child)."""

        if self.child_running:
            return (
                False,
                (
                    "The guided calibrator is still running; close it (or use its result) "
                    "before cancelling setup. The child process is never terminated."
                ),
            )
        return True, ""

    def finish_allowed(self) -> tuple[bool, str]:
        """Return whether Finish may run the single commit boundary."""

        if self.child_running:
            return False, "The guided calibrator is still running; wait for it to close."
        if self.blocked:
            return False, self.preflight.message
        validation = self.keymap_validation()
        if not validation.valid:
            return (
                False,
                f"The keymap is not ready ({validation.reason}); complete calibration first.",
            )
        return True, ""

    def finish(self, callbacks: SetupCommitCallbacks) -> FinishResult:
        """Run the single commit boundary; gated failures never reach it."""

        allowed, message = self.finish_allowed()
        if not allowed:
            self.last_message = message
            return FinishResult(ok=False, stage="gate", message=message, rolled_back=False)
        result = finish_setup(self.draft, callbacks)
        self.last_message = "" if result.ok else result.message
        return result
