"""Low-level atomic read/write of reactive brightness transition state.

Extracted from ``_render_brightness_support.py`` (WS1 / A4 slice 1). These
three operations take a ``ReactiveRenderState`` and a ``threading.Lock``
directly — they do not perform engine attribute resolution. The higher-
level engine-attr clear path (``clear_transition_state``) stays in the
parent module because it routes writes through ``set_engine_attr``.

Concurrent reads and writes are guarded by the supplied lock so the
render thread can read transition fields while another thread seeds a
new transition (e.g. via idle-power dim/restore).
"""

from __future__ import annotations

import threading

from ._render_brightness_support import ReactiveRenderState


def seed_transition_atomic(
    state: ReactiveRenderState,
    lock: threading.Lock,
    *,
    from_brightness: int,
    to_brightness: int,
    started_at: float,
    duration_s: float,
) -> None:
    with lock:
        state._reactive_transition_from_brightness = from_brightness
        state._reactive_transition_to_brightness = to_brightness
        state._reactive_transition_started_at = started_at
        state._reactive_transition_duration_s = duration_s


def read_transition_atomic(
    state: ReactiveRenderState,
    lock: threading.Lock,
) -> tuple[int | None, int | None, float | None, float | None]:
    with lock:
        return (
            state._reactive_transition_from_brightness,
            state._reactive_transition_to_brightness,
            state._reactive_transition_started_at,
            state._reactive_transition_duration_s,
        )


def clear_transition_atomic(
    state: ReactiveRenderState,
    lock: threading.Lock,
) -> None:
    with lock:
        state._reactive_transition_from_brightness = None
        state._reactive_transition_to_brightness = None
        state._reactive_transition_started_at = None
        state._reactive_transition_duration_s = None


__all__ = [
    "clear_transition_atomic",
    "read_transition_atomic",
    "seed_transition_atomic",
]
