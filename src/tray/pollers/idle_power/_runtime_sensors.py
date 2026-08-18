"""Idle-power dim/idle sensor readers (Wayland, evdev, logind).

Extracted from ``_runtime.py`` (WS1 / A7 slice 1).
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from ._constants import WAYLAND_IDLE_RECONNECT_BACKOFF_S, WAYLAND_IDLE_RECONNECT_FAILURE_THRESHOLD
from ._input_idle import InputIdleTracker

_IDLE_POWER_RUNTIME_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


def read_session_idle_state(
    *,
    session_id: str | None,
    idle_timeout_s: float,
    read_logind_idle_seconds_fn: Callable[..., float | None],
) -> bool | None:
    if not session_id:
        return None
    idle_s = read_logind_idle_seconds_fn(session_id=session_id)
    if idle_s is None:
        return None
    return bool(float(idle_s) >= float(idle_timeout_s))


def _wayland_idle_now() -> float:
    return float(time.monotonic())


def _note_wayland_idle_failure(loop_state: object, *, now: float) -> None:
    try:
        previous = getattr(loop_state, "wayland_idle_fail_count", 0) or 0
        fail_count = int(previous) + 1
    except (TypeError, ValueError):
        fail_count = 1
    setattr(loop_state, "wayland_idle_fail_count", fail_count)  # noqa: B010 - loop state is duck-typed
    if fail_count < int(WAYLAND_IDLE_RECONNECT_FAILURE_THRESHOLD):
        return
    setattr(  # noqa: B010 - loop state is duck-typed
        loop_state,
        "wayland_idle_retry_at",
        float(now) + float(WAYLAND_IDLE_RECONNECT_BACKOFF_S),
    )


def _wayland_idle_retry_blocked(loop_state: object, *, now: float) -> bool:
    try:
        retry_at = float(getattr(loop_state, "wayland_idle_retry_at", 0.0) or 0.0)
    except (TypeError, ValueError):
        return False
    return retry_at > float(now)


def read_wayland_dimmed_state(
    *,
    loop_state: object,
    timeout_s: float,
    create_wayland_idle_tracker_fn: Callable[[int], Any | None],
    read_wayland_idle_fn: Callable[[Any], bool | None],
    monotonic_fn: Callable[[], float] = _wayland_idle_now,
) -> bool | None:
    timeout_ms = int(float(timeout_s) * 1000)
    if timeout_ms <= 0:
        return None

    now = float(monotonic_fn())
    wayland_idle_tracker = getattr(loop_state, "wayland_idle_tracker", None)
    if wayland_idle_tracker is None:
        if _wayland_idle_retry_blocked(loop_state, now=now):
            return None
        try:
            wayland_idle_tracker = create_wayland_idle_tracker_fn(timeout_ms)
            setattr(loop_state, "wayland_idle_tracker", wayland_idle_tracker)  # noqa: B010 - loop state is duck-typed
        except _IDLE_POWER_RUNTIME_EXCEPTIONS:
            _note_wayland_idle_failure(loop_state, now=now)
            setattr(loop_state, "wayland_idle_tracker", None)  # noqa: B010 - loop state is duck-typed
            return None
        if wayland_idle_tracker is None:
            _note_wayland_idle_failure(loop_state, now=now)
            return None

    tracker = wayland_idle_tracker
    if tracker is None:
        return None

    try:
        set_timeout_ms = getattr(tracker, "set_timeout_ms", None)
        if callable(set_timeout_ms):
            set_timeout_ms(timeout_ms)
    except _IDLE_POWER_RUNTIME_EXCEPTIONS:
        pass

    result = read_wayland_idle_fn(tracker)
    if result is None:
        # The tracker's Wayland connection is broken (is_idle returned
        # None after a dispatch/read/flush failure).  Close and drop the
        # cached tracker so a later poll can recreate a fresh connection
        # instead of reusing a dead proxy for the entire session — which
        # would silently fall back to the brightness heuristic. Repeated
        # failures back off so a protocol error cannot reconnect-storm KWin.
        try:
            close = getattr(tracker, "close", None)
            if callable(close):
                close()
        except _IDLE_POWER_RUNTIME_EXCEPTIONS:
            pass
        _note_wayland_idle_failure(loop_state, now=now)
        setattr(loop_state, "wayland_idle_tracker", None)  # noqa: B010 - loop state is duck-typed
        return None

    setattr(loop_state, "wayland_idle_fail_count", 0)  # noqa: B010 - loop state is duck-typed
    return result


def read_desktop_dimmed_state(
    *,
    loop_state: object,
    on_ac_power: bool | None,
    read_desktop_dim_timeout_fn: Callable[[bool | None], float | None],
    create_wayland_idle_tracker_fn: Callable[[int], Any | None],
    read_wayland_idle_fn: Callable[[Any], bool | None],
    create_input_idle_tracker_fn: Callable[[], InputIdleTracker],
    read_input_idle_seconds_fn: Callable[[InputIdleTracker], float | None],
    fallback_timeout_s: float,
) -> tuple[bool | None, bool | None]:
    """Use KDE/system dim timeout + session idle as the primary dim signal.

    Prefers the Wayland idle notifier when available (it sees touchpad and
    other input devices that raw evdev cannot).  Falls back to evdev input
    idle on X11 or when the compositor does not expose the protocol.

    When the desktop dim timeout is not configured (e.g. KDE's
    ``DimDisplayIdleTimeoutSec`` is absent for the active power profile),
    the ``fallback_timeout_s`` (the general idle timeout) is used instead so
    that the Wayland tracker / evdev path is still consulted.  This prevents
    the brightness heuristic from firing on manual screen-brightness changes
    when a real idle source is available but the desktop dim policy is off.

    Returns (dimmed, session_idle).  If no timeout or idle source is
    available, returns (None, None) so the caller can fall back.
    """

    timeout_s = read_desktop_dim_timeout_fn(on_ac_power)
    if timeout_s is None:
        timeout_s = float(fallback_timeout_s) if float(fallback_timeout_s) > 0 else None
    if timeout_s is None:
        return None, None

    wayland_idle = read_wayland_dimmed_state(
        loop_state=loop_state,
        timeout_s=timeout_s,
        create_wayland_idle_tracker_fn=create_wayland_idle_tracker_fn,
        read_wayland_idle_fn=read_wayland_idle_fn,
    )
    if wayland_idle is not None:
        dimmed = bool(wayland_idle)
        return dimmed, dimmed

    input_idle_tracker = getattr(loop_state, "input_idle_tracker", None)
    if input_idle_tracker is None:
        try:
            input_idle_tracker = create_input_idle_tracker_fn()
            setattr(loop_state, "input_idle_tracker", input_idle_tracker)  # noqa: B010 - loop state is duck-typed
        except _IDLE_POWER_RUNTIME_EXCEPTIONS:
            return None, None

    input_idle_s = read_input_idle_seconds_fn(input_idle_tracker)
    if input_idle_s is None:
        return None, None

    dimmed = bool(float(input_idle_s) >= float(timeout_s))
    return dimmed, dimmed
