"""Idle-power dim/idle sensor readers (Wayland, evdev, logind).

Extracted from ``_runtime.py`` (WS1 / A7 slice 1).
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from ._input_idle import InputIdleTracker


_IDLE_POWER_RUNTIME_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


def read_session_idle_state(
    *,
    session_id: str | None,
    idle_timeout_s: float,
    read_logind_idle_seconds_fn: Callable[..., Optional[float]],
) -> Optional[bool]:
    if not session_id:
        return None
    idle_s = read_logind_idle_seconds_fn(session_id=session_id)
    if idle_s is None:
        return None
    return bool(float(idle_s) >= float(idle_timeout_s))


def read_wayland_dimmed_state(
    *,
    loop_state: object,
    timeout_s: float,
    create_wayland_idle_tracker_fn: Callable[[int], Optional[Any]],
    read_wayland_idle_fn: Callable[[Any], Optional[bool]],
) -> Optional[bool]:
    timeout_ms = int(float(timeout_s) * 1000)
    if timeout_ms <= 0:
        return None

    wayland_idle_tracker = getattr(loop_state, "wayland_idle_tracker", None)
    if wayland_idle_tracker is None:
        try:
            wayland_idle_tracker = create_wayland_idle_tracker_fn(timeout_ms)
            setattr(loop_state, "wayland_idle_tracker", wayland_idle_tracker)
        except _IDLE_POWER_RUNTIME_EXCEPTIONS:
            setattr(loop_state, "wayland_idle_tracker", None)
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
        # cached tracker so the next poll recreates a fresh connection
        # instead of reusing a dead proxy for the entire session — which
        # would silently fall back to the brightness heuristic.
        try:
            close = getattr(tracker, "close", None)
            if callable(close):
                close()
        except _IDLE_POWER_RUNTIME_EXCEPTIONS:
            pass
        setattr(loop_state, "wayland_idle_tracker", None)

    return result


def read_desktop_dimmed_state(
    *,
    loop_state: object,
    on_ac_power: Optional[bool],
    read_desktop_dim_timeout_fn: Callable[[Optional[bool]], Optional[float]],
    create_wayland_idle_tracker_fn: Callable[[int], Optional[Any]],
    read_wayland_idle_fn: Callable[[Any], Optional[bool]],
    create_input_idle_tracker_fn: Callable[[], InputIdleTracker],
    read_input_idle_seconds_fn: Callable[[InputIdleTracker], Optional[float]],
    fallback_timeout_s: float,
) -> tuple[Optional[bool], Optional[bool]]:
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
            setattr(loop_state, "input_idle_tracker", input_idle_tracker)
        except _IDLE_POWER_RUNTIME_EXCEPTIONS:
            return None, None

    input_idle_s = read_input_idle_seconds_fn(input_idle_tracker)
    if input_idle_s is None:
        return None, None

    dimmed = bool(float(input_idle_s) >= float(timeout_s))
    return dimmed, dimmed
