from __future__ import annotations

import os
from typing import Optional


_RECOVERABLE_PROBE_EXCEPTIONS = (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError)


def detect_idle_power_source() -> str:
    """Return a short human-readable label for the idle source in use.

    This is a best-effort probe intended for the settings UI and diagnostics.
    It does not mutate tray runtime state; it simply tries each candidate source
    in priority order and reports the first one that appears usable in the
    current session.
    """

    if _wayland_idle_available():
        return "Wayland compositor idle"

    if _evdev_input_idle_available():
        return "evdev input devices"

    return "system idle / brightness heuristic"


def _wayland_idle_available() -> bool:
    """True if a Wayland compositor with ext-idle-notify-v1 is reachable."""

    if not (os.environ.get("WAYLAND_DISPLAY") or os.environ.get("WAYLAND_SOCKET")):
        return False

    try:
        from src.tray.pollers.idle_power._wayland_idle import create_wayland_idle_tracker

        tracker = create_wayland_idle_tracker(timeout_ms=1000)
        if tracker is not None:
            tracker.close()
            return True
    except _RECOVERABLE_PROBE_EXCEPTIONS:
        pass

    return False


def _evdev_input_idle_available() -> bool:
    """True if at least one user input evdev node is readable."""

    try:
        from src.tray.pollers.idle_power._input_idle import InputIdleTracker

        tracker = InputIdleTracker()
        try:
            idle = tracker.seconds_since_activity()
            return idle is not None
        finally:
            tracker.close()
    except _RECOVERABLE_PROBE_EXCEPTIONS:
        pass

    return False


def format_idle_power_source(source: Optional[str]) -> str:
    """Format an idle-source label for display, with a safe fallback."""

    if not source:
        return "Unknown"
    return str(source)
