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
    from src.core.effects.engine import EffectsEngine

logger = logging.getLogger(__name__)


def _monotonic() -> float:
    # Resolve through render.time so existing test monkeypatches keep working.
    from . import render as render_module

    return float(render_module.time.monotonic())


def post_restore_frame_scale(engine: "EffectsEngine") -> float:
    """Whole-frame scale in [FRAME_MIN, 1] while restore damp remaining > 0."""

    damp, remaining_s = post_restore_visual_damp(engine)
    if remaining_s <= 0.0 or float(damp) >= 0.999:
        return 1.0
    min_pulse = float(POST_RESTORE_PULSE_VISUAL_MIN_FACTOR)
    min_frame = float(POST_RESTORE_FRAME_MIN_FACTOR)
    # Map pulse damp [min_pulse, 1] → frame [min_frame, 1].
    t = (float(damp) - min_pulse) / max(1e-6, 1.0 - min_pulse)
    t = max(0.0, min(1.0, t))
    return min_frame + ((1.0 - min_frame) * t)


def post_restore_visual_damp(engine: "EffectsEngine") -> tuple[float, float]:
    """Compute the visual damp factor and remaining seconds for post-restore.

    After an idle wake or temp-dim restore, hardware brightness ramps up from a
    low value. Full-intensity reactive pulses (and, via frame scale, soft-on
    matrix steps) would flash. This returns a damp factor (0..1) for the active
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
