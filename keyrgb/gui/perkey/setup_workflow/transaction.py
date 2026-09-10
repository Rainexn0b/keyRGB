"""UX-04 finish transaction: one explicit commit boundary with rollback.

Ordering is explicit: ``apply_draft`` (in-memory editor/config state), then
``persist`` (profile/config writes), then the optional ``apply_hardware``
push. If any stage raises an expected persistence/runtime error, the
original snapshot is restored via ``restore_original`` and a structured
failure is returned with the workflow left open (the draft is untouched, so
the user can fix and retry). Unexpected ``Exception`` failures still trigger
a rollback attempt first, then propagate (interpreter-level ``BaseException``
exits propagate immediately: state cannot be safely restored during
teardown). A failed rollback never silently succeeds:
its diagnostic context is preserved on the result (expected path) or chained
(``raise ... from ...``, unexpected path).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from .model import SetupDraft, SetupSnapshot, snapshot_copy

__all__ = [
    "DEFAULT_EXPECTED_ERRORS",
    "FinishResult",
    "SetupCommitCallbacks",
    "finish_setup",
]

logger = logging.getLogger(__name__)

# Narrow typed boundary for expected finish failures: persistence (OSError),
# rejected values (ValueError), and runtime apply problems (RuntimeError).
# Restricted to ``Exception`` subclasses so interpreter-level exits such as
# KeyboardInterrupt/SystemExit can never be configured into the caught
# boundary. Callers may widen/narrow within ``Exception`` via the
# ``expected_errors`` parameter instead of catching broad ``Exception``.
DEFAULT_EXPECTED_ERRORS: tuple[type[Exception], ...] = (OSError, RuntimeError, ValueError)


@dataclass(frozen=True)
class SetupCommitCallbacks:
    """Injected narrow callbacks; keeps this core free of editor internals."""

    apply_draft: Callable[[SetupDraft], None]
    persist: Callable[[SetupDraft], None]
    restore_original: Callable[[SetupSnapshot], None]
    apply_hardware: Callable[[SetupDraft], None] | None = None


@dataclass(frozen=True)
class FinishResult:
    """Structured finish outcome; ``ok`` is True only if all stages wrote."""

    ok: bool
    stage: str
    message: str
    rolled_back: bool = False
    error: Exception | None = field(default=None, compare=False)
    restore_error: Exception | None = field(default=None, compare=False)


def finish_setup(
    draft: SetupDraft,
    callbacks: SetupCommitCallbacks,
    *,
    expected_errors: tuple[type[Exception], ...] = DEFAULT_EXPECTED_ERRORS,
) -> FinishResult:
    """Run the single commit boundary; Back/Next/Cancel never reach here."""
    if not isinstance(callbacks, SetupCommitCallbacks):
        raise TypeError("callbacks must be a SetupCommitCallbacks")
    if not expected_errors or not all(
        isinstance(item, type) and issubclass(item, Exception) for item in expected_errors
    ):
        raise TypeError("expected_errors must be a non-empty tuple of Exception subclasses")

    try:
        stage = "apply_draft"
        callbacks.apply_draft(draft)
        stage = "persist"
        callbacks.persist(draft)
        if callbacks.apply_hardware is not None:
            stage = "apply_hardware"
            callbacks.apply_hardware(draft)
    except expected_errors as exc:
        return _rollback_and_fail(snapshot_copy(draft.original), callbacks, stage, exc)
    except Exception as unexpected:  # @quality-exception exception-transparency: injected stage callbacks are unbounded so unexpected failures cannot be enumerated; rollback is attempted, then the original propagates (never swallowed)
        try:
            callbacks.restore_original(snapshot_copy(draft.original))
        except Exception as restore_exc:  # @quality-exception exception-transparency: injected restore callback is unbounded; chained via `raise ... from ...` so both failures stay visible
            raise restore_exc from unexpected
        raise
    return FinishResult(ok=True, stage="committed", message="setup committed")


def _rollback_and_fail(
    snapshot: SetupSnapshot,
    callbacks: SetupCommitCallbacks,
    stage: str,
    error: Exception,
) -> FinishResult:
    try:
        callbacks.restore_original(snapshot)
    except Exception as restore_exc:  # noqa: BLE001  # @quality-exception exception-transparency: injected restore callback is unbounded so it cannot be narrowed; the failure is preserved on the result, never swallowed
        # Preserve diagnostic context instead of silently succeeding: the
        # workflow stays open with both the stage error and the rollback error.
        logger.debug("setup finish rollback failed after %s error: %s", stage, restore_exc)
        return FinishResult(
            ok=False,
            stage=stage,
            message=f"setup failed at {stage} and rollback failed: {error!r}",
            rolled_back=False,
            error=error,
            restore_error=restore_exc,
        )
    return FinishResult(
        ok=False,
        stage=stage,
        message=f"setup failed at {stage}; original state restored: {error!r}",
        rolled_back=True,
        error=error,
    )
