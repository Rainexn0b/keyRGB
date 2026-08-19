"""Shared cooperative-shutdown helpers for tray polling threads."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, cast


class _ShutdownEvent(Protocol):
    def is_set(self) -> bool: ...

    def wait(self, timeout: float | None = None) -> bool: ...


def _shutdown_event_or_none(tray: object) -> _ShutdownEvent | None:
    try:
        event = vars(tray).get("_polling_shutdown_event")
    except TypeError:
        return None
    if not callable(getattr(event, "is_set", None)) or not callable(getattr(event, "wait", None)):
        return None
    return cast(_ShutdownEvent, event)


def shutdown_requested(tray: object) -> bool:
    """Return whether the tray polling runtime is shutting down."""

    event = _shutdown_event_or_none(tray)
    return bool(event is not None and event.is_set())


def wait_for_shutdown(
    tray: object,
    timeout_s: float,
    *,
    sleep_fn: Callable[[float], None],
) -> bool:
    """Wait interruptibly for shutdown, falling back to the supplied sleeper."""

    event = _shutdown_event_or_none(tray)
    if event is not None:
        return bool(event.wait(max(0.0, float(timeout_s))))
    sleep_fn(float(timeout_s))
    return False
