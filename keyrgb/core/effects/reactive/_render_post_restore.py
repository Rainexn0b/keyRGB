"""Post-restore visual damp for reactive rendering.

Extracted from ``render.py`` (WS1 follow-up): keeps restore-window pulse/frame
damp math separate from the main render orchestration surface.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from . import _render_brightness_support as _support
from ._constants import (
    POST_RESTORE_FRAME_MIN_FACTOR,
    POST_RESTORE_PULSE_VISUAL_HOLDOFF_S,
    POST_RESTORE_PULSE_VISUAL_MIN_FACTOR,
)

if TYPE_CHECKING:
    from keyrgb.core.effects.engine import EffectsEngine

logger = logging.getLogger(__name__)


def _monotonic() -> float:
    # Resolve through render.time so existing test monkeypatches keep working.
    from . import render as render_module

    return float(render_module.time.monotonic())


def post_restore_frame_scale(engine: EffectsEngine) -> float:
    """Whole-frame scale in [FRAME_MIN, 1] while restore frame envelope is active.

    Independent of the pulse restore phase; monotonic from FRAME_MIN to 1.0
    over the configured fade duration. Pulse damp may continue after this
    envelope ends.
    """

    raw_started = _support.read_engine_attr(
        engine,
        "_reactive_restore_frame_started_at",
        missing_default=None,
        error_default=None,
        logger=logger,
    )
    raw_duration = _support.read_engine_attr(
        engine,
        "_reactive_restore_frame_duration_s",
        missing_default=None,
        error_default=None,
        logger=logger,
    )
    started_s = _support.coerce_float(raw_started, default=None) if raw_started is not None else None
    duration_s = _support.coerce_float(raw_duration, default=None) if raw_duration is not None else None
    if started_s is None or duration_s is None:
        return 1.0
    duration_f = max(0.0, float(duration_s))
    if duration_f <= 0.0:
        return 1.0
    started_f = float(started_s)
    elapsed = max(0.0, float(_monotonic()) - started_f)
    if elapsed >= duration_f:
        # Envelope completed; whole-frame returns to full. Lazy clear is not
        # required for correctness but keeps state tidy for diagnostics.
        return 1.0
    progress = max(0.0, min(1.0, elapsed / duration_f))
    min_frame = float(POST_RESTORE_FRAME_MIN_FACTOR)
    return min_frame + ((1.0 - min_frame) * progress)


def post_restore_visual_damp(engine: EffectsEngine) -> tuple[float, float]:
    """Compute the visual damp factor and remaining seconds for post-restore.

    After an idle wake or temp-dim restore, hardware brightness ramps up from a
    low value. Full-intensity reactive pulses would flash. This returns a damp
    factor (0..1) for the active
    restore window seeded at idle restore (FIRST_PULSE_PENDING), extended on the
    first post-restore keypress (→ DAMPING). When inactive, damp is 1.0.

    Returns:
        (damp_factor, remaining_seconds) — damp_factor is 1.0 when no damp
        is active; remaining_seconds is 0.0 when no damp is active.
    """
    restore_phase = _support.restore_phase_or_default(
        engine,
        default=_support.ReactiveRestorePhase.NORMAL,
        logger=logger,
    )
    if restore_phase is _support.ReactiveRestorePhase.NORMAL:
        return 1.0, 0.0

    raw_until = _support.read_engine_attr(
        engine,
        "_reactive_restore_damp_until",
        missing_default=None,
        error_default=None,
        logger=logger,
    )
    until_s = _support.coerce_float(raw_until, default=None)
    if until_s is None:
        if restore_phase is _support.ReactiveRestorePhase.DAMPING:
            _support.set_engine_attr(
                engine,
                "_reactive_restore_phase",
                _support.ReactiveRestorePhase.NORMAL,
                logger=logger,
            )
        return 1.0, 0.0

    remaining_s = max(0.0, float(until_s) - _monotonic())
    if remaining_s <= 0.0:
        if restore_phase is _support.ReactiveRestorePhase.DAMPING:
            _support.set_engine_attr(
                engine,
                "_reactive_restore_phase",
                _support.ReactiveRestorePhase.NORMAL,
                logger=logger,
            )
            _support.set_engine_attr(engine, "_reactive_restore_damp_until", None, logger=logger)
        return 1.0, 0.0

    progress = 1.0 - min(1.0, remaining_s / POST_RESTORE_PULSE_VISUAL_HOLDOFF_S)
    damp = POST_RESTORE_PULSE_VISUAL_MIN_FACTOR + ((1.0 - POST_RESTORE_PULSE_VISUAL_MIN_FACTOR) * progress)
    return damp, remaining_s
