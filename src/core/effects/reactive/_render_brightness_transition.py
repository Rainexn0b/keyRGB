"""Reactive brightness transition progress and visual scale.

Extracted from ``_render_brightness.py`` (WS1 / A5 slice 1). Owns the
in-flight transition read path used by temp-dim / idle-restore ramps.
The parent module re-exports public names for stable import paths.
"""

from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING, Callable, Optional

from . import _render_brightness_support as _support

if TYPE_CHECKING:
    from src.core.effects.engine import EffectsEngine


_LOGGER = logging.getLogger(__name__)


def resolve_reactive_transition_brightness(
    engine: "EffectsEngine",
    *,
    clamp01_fn: Callable[[float], float],
) -> Optional[tuple[int, bool]]:
    """Return the current transition brightness for reactive temp-dim flows."""

    transition = _resolve_reactive_transition_progress(engine, clamp01_fn=clamp01_fn)
    if transition is None:
        return None

    current_f, rising = transition
    if rising:
        return int(math.ceil(current_f)), True

    return int(round(current_f)), False


def resolve_reactive_transition_visual_scale(
    engine: "EffectsEngine",
    *,
    clamp01_fn: Callable[[float], float],
) -> float:
    """Return a fractional scale for rising per-key transitions.

    During low-brightness restore ramps the hardware brightness must stay
    integer-valued, which can make `1 -> 5` restores visibly step.  We smooth
    the written per-key frame by scaling it against the ceiled transition level
    so the overall visible intensity can still move fractionally between those
    hardware steps.
    """

    transition = _resolve_reactive_transition_progress(engine, clamp01_fn=clamp01_fn)
    if transition is None:
        return 1.0

    current_f, rising = transition
    if not rising:
        return 1.0

    quantized = int(math.ceil(current_f))
    if quantized <= 0:
        return 0.0

    return clamp01_fn(float(current_f) / float(quantized))


def _resolve_reactive_transition_progress(
    engine: "EffectsEngine",
    *,
    clamp01_fn: Callable[[float], float],
) -> Optional[tuple[float, bool]]:
    """Return the in-flight reactive transition brightness as a float."""

    state = _support.ensure_reactive_state(engine)
    lock = getattr(engine, "reactive_lock", None)
    start: object
    end: object
    started_at: object
    duration_s: object
    if lock is not None:
        start, end, started_at, duration_s = _support.read_transition_atomic(state, lock)
    else:
        start = _support.read_engine_attr(
            engine,
            "_reactive_transition_from_brightness",
            missing_default=None,
            error_default=None,
        )
        end = _support.read_engine_attr(
            engine,
            "_reactive_transition_to_brightness",
            missing_default=None,
            error_default=None,
        )
        started_at = _support.read_engine_attr(
            engine,
            "_reactive_transition_started_at",
            missing_default=None,
            error_default=None,
        )
        duration_s = _support.read_engine_attr(
            engine,
            "_reactive_transition_duration_s",
            missing_default=None,
            error_default=None,
        )

    if start is None or end is None or started_at is None or duration_s is None:
        return None

    start_i = _support.coerce_brightness(start, default=None)
    end_i = _support.coerce_brightness(end, default=None)
    duration = _support.coerce_float(duration_s, default=None)
    started = _support.coerce_float(started_at, default=None)
    if start_i is None or end_i is None or duration is None or started is None:
        return None

    duration = max(0.0, duration)
    rising = bool(end_i >= start_i)

    if duration <= 0.0 or start_i == end_i:
        if lock is not None:
            _support.clear_transition_atomic(state, lock)
        else:
            _support.clear_transition_state(engine, logger=_LOGGER)
        return float(end_i), rising

    elapsed = max(0.0, float(time.monotonic()) - started)
    if elapsed >= duration:
        if lock is not None:
            _support.clear_transition_atomic(state, lock)
        else:
            _support.clear_transition_state(engine, logger=_LOGGER)
        return float(end_i), rising

    t = clamp01_fn(elapsed / duration)
    current = float(start_i) + (float(end_i - start_i) * t)
    return current, rising


def _clear_transition_state(engine: "EffectsEngine") -> None:
    state = _support.ensure_reactive_state(engine)
    lock = getattr(engine, "reactive_lock", None)
    if lock is not None:
        _support.clear_transition_atomic(state, lock)
    else:
        _support.clear_transition_state(engine, logger=_LOGGER)
