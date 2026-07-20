"""Restore-seed queue for reactive brightness transitions.

Extracted from ``_render_brightness_support.py`` (WS1 / A4 slice 1) to drop
the parent module below the REFACTOR LOC band without changing behavior.

This module owns the "seed" abstraction used to propagate restore damp
timers across the ``ReactiveRenderState`` reset that ``engine.stop()``
triggers. Without it, the render thread's first frames after a restart
would race the post-start seeding and lose the damp window, causing a
bright flash on idle wake. The parent module re-exports these names so
existing import paths and module-attribute access
(``_support.seed_reactive_restore_windows`` etc.) keep working.
"""

from __future__ import annotations

from dataclasses import dataclass
import time

from ._render_brightness_support import (
    ReactiveRestorePhase,
    ensure_reactive_state,
)


_PENDING_RESTORE_SEED_ATTR = "_pending_reactive_restore_seed"


@dataclass(frozen=True, slots=True)
class ReactiveRestoreSeed:
    """Restore damp timers applied onto a fresh ReactiveRenderState after stop()."""

    disable_pulse_hw_lift_until: float
    restore_damp_until: float
    restore_phase: ReactiveRestorePhase = ReactiveRestorePhase.FIRST_PULSE_PENDING


def build_reactive_restore_seed(*, fade_in_duration_s: float, now: float | None = None) -> ReactiveRestoreSeed:
    """Build restore damp timers for idle full-off → on wake."""

    current = float(time.monotonic() if now is None else now)
    fade_s = float(fade_in_duration_s)
    return ReactiveRestoreSeed(
        disable_pulse_hw_lift_until=current + max(2.0, fade_s + 0.75),
        restore_damp_until=current + max(4.0, fade_s + 2.75),
        restore_phase=ReactiveRestorePhase.FIRST_PULSE_PENDING,
    )


def queue_reactive_restore_seed(engine: object, seed: ReactiveRestoreSeed) -> None:
    """Queue a seed so the next ``ReactiveRenderState()`` reset inherits it.

    ``engine.stop()`` rebuilds reactive state and would otherwise clear restore
    damp before the render thread's first frames, racing post-start seeding.
    """

    try:
        setattr(engine, _PENDING_RESTORE_SEED_ATTR, seed)
    except (AttributeError, TypeError):
        return


def apply_queued_reactive_restore_seed(engine: object) -> bool:
    """Apply and clear a queued restore seed onto the current reactive state."""

    try:
        seed = getattr(engine, _PENDING_RESTORE_SEED_ATTR, None)
    except (AttributeError, TypeError):
        return False
    if not isinstance(seed, ReactiveRestoreSeed):
        return False
    try:
        setattr(engine, _PENDING_RESTORE_SEED_ATTR, None)
    except (AttributeError, TypeError):
        pass
    return apply_reactive_restore_seed(engine, seed)


def apply_reactive_restore_seed(engine: object, seed: ReactiveRestoreSeed) -> bool:
    """Write restore damp timers onto the live reactive state."""

    try:
        state = ensure_reactive_state(engine)
        state._reactive_disable_pulse_hw_lift_until = float(seed.disable_pulse_hw_lift_until)
        state._reactive_restore_damp_until = float(seed.restore_damp_until)
        state._reactive_restore_phase = seed.restore_phase
        return True
    except (AttributeError, TypeError, ValueError):
        return False


def seed_reactive_restore_windows(engine: object, *, fade_in_duration_s: float, now: float | None = None) -> bool:
    """Queue + apply restore damp (call before and after effect start on idle wake)."""

    seed = build_reactive_restore_seed(fade_in_duration_s=fade_in_duration_s, now=now)
    queue_reactive_restore_seed(engine, seed)
    return apply_reactive_restore_seed(engine, seed)


__all__ = [
    "ReactiveRestoreSeed",
    "apply_queued_reactive_restore_seed",
    "apply_reactive_restore_seed",
    "build_reactive_restore_seed",
    "queue_reactive_restore_seed",
    "seed_reactive_restore_windows",
]
