from __future__ import annotations

import logging
import select
import threading
from collections.abc import Sequence
from typing import Any, Callable, Optional


_SelectFn = Callable[..., tuple[Sequence[object], Sequence[object], Sequence[object]]]


_RECOVERABLE_WAYLAND_EXCEPTIONS = (AttributeError, ImportError, OSError, RuntimeError, TypeError, ValueError)

logger = logging.getLogger(__name__)


class WaylandIdleTracker:
    """Session-level idle tracker using the Wayland ext-idle-notify-v1 protocol.

    This is the preferred idle source on Wayland compositors (including KDE
    KWin) because it tracks activity at the compositor level, including devices
    such as touchpads that are exclusively grabbed by libinput and therefore
    invisible to raw evdev readers.
    """

    def __init__(
        self,
        timeout_ms: int = 10_000,
        display_name_or_fd: int | str | None = None,
        select_fn: _SelectFn = select.select,
    ) -> None:
        self._timeout_ms = int(timeout_ms)
        self._display_name_or_fd = display_name_or_fd
        self._select_fn = select_fn
        self._lock = threading.Lock()
        self._idle = False
        self._available = False

        self._display: Optional[Any] = None
        self._idle_notifier: Optional[Any] = None
        self._seat: Optional[Any] = None
        self._notification: Optional[Any] = None

        self._setup()

    def _setup(self) -> None:
        try:
            from pywayland.client import Display
            from pywayland.protocol.ext_idle_notify_v1 import ExtIdleNotifierV1
            from pywayland.protocol.wayland import WlSeat
        except _RECOVERABLE_WAYLAND_EXCEPTIONS as exc:
            raise RuntimeError(f"Wayland protocol support unavailable: {exc}") from exc

        display = Display(self._display_name_or_fd)
        display.connect()

        registry = display.get_registry()

        found: dict[str, Optional[int]] = {"seat": None, "notifier": None}

        def _on_global(registry_proxy: object, name: int, interface: str, version: int) -> None:
            if interface == WlSeat.name and found["seat"] is None:
                found["seat"] = name
            elif interface == ExtIdleNotifierV1.name and found["notifier"] is None:
                found["notifier"] = name

        registry.dispatcher["global"] = _on_global
        display.roundtrip()

        seat_global_name = found["seat"]
        notifier_global_name = found["notifier"]
        if seat_global_name is None or notifier_global_name is None:
            display.disconnect()
            raise RuntimeError("Required Wayland globals (wl_seat, ext_idle_notifier_v1) not available")

        self._display = display
        self._seat = registry.bind(seat_global_name, WlSeat, WlSeat.version)
        self._idle_notifier = registry.bind(notifier_global_name, ExtIdleNotifierV1, ExtIdleNotifierV1.version)
        self._available = True
        logger.info("Wayland idle tracker connected (timeout=%d ms)", self._timeout_ms)

        self._create_notification()

    def _create_notification(self) -> None:
        if self._notification is not None:
            try:
                self._notification.destroy()
            except _RECOVERABLE_WAYLAND_EXCEPTIONS:
                pass
            self._notification = None

        if self._idle_notifier is None or self._seat is None:
            return

        # A new notification starts in the non-idle state. Reset our local
        # state so we wait for the compositor to send an idled event.
        with self._lock:
            self._idle = False

        notification = self._idle_notifier.get_idle_notification(self._timeout_ms, self._seat)

        def _on_idled(_proxy: object) -> None:
            with self._lock:
                self._idle = True
            logger.debug("Wayland idle notifier: idled")

        def _on_resumed(_proxy: object) -> None:
            with self._lock:
                self._idle = False
            logger.debug("Wayland idle notifier: resumed")

        notification.dispatcher["idled"] = _on_idled
        notification.dispatcher["resumed"] = _on_resumed

        self._notification = notification
        if self._display is not None:
            self._display.flush()

    def set_timeout_ms(self, timeout_ms: int) -> None:
        timeout_ms = int(timeout_ms)
        if timeout_ms == self._timeout_ms:
            return
        self._timeout_ms = timeout_ms
        if self._available:
            self._create_notification()

    def _dispatch_pending(self) -> bool:
        """Dispatch events already in the Wayland queue. Returns False on error."""
        if self._display is None:
            return False
        try:
            self._display.dispatch(block=False)
            return True
        except _RECOVERABLE_WAYLAND_EXCEPTIONS:
            return False

    def _read_and_dispatch(self) -> bool:
        """Read events from the display fd and dispatch them. Returns False on error."""
        if self._display is None:
            return False
        try:
            fd = self._display.get_fd()
            readable, _, _ = self._select_fn([fd], [], [], 0)
            if readable:
                self._display.read()
            return self._dispatch_pending()
        except _RECOVERABLE_WAYLAND_EXCEPTIONS:
            return False

    def is_idle(self) -> Optional[bool]:
        """Return current idle state, dispatching any pending Wayland events.

        Returns ``True`` if the session has been idle for at least the
        configured timeout, ``False`` if active, or ``None`` if the Wayland
        connection has failed.
        """
        if not self._available or self._display is None:
            return None

        if not self._dispatch_pending():
            self._available = False
            return None

        if not self._read_and_dispatch():
            self._available = False
            return None

        try:
            self._display.flush()
        except _RECOVERABLE_WAYLAND_EXCEPTIONS:
            self._available = False
            return None

        with self._lock:
            return bool(self._idle)

    def __del__(self) -> None:
        # Best-effort cleanup if the tracker is garbage collected without an
        # explicit close(). This prevents libwayland proxy destruction crashes
        # when Python's GC collects the display and its proxies out of order.
        try:
            self.close()
        except _RECOVERABLE_WAYLAND_EXCEPTIONS:
            pass

    def close(self) -> None:
        if self._notification is not None:
            try:
                self._notification.destroy()
            except _RECOVERABLE_WAYLAND_EXCEPTIONS:
                pass
            self._notification = None

        self._idle_notifier = None
        self._seat = None
        self._available = False

        if self._display is not None:
            try:
                self._display.disconnect()
            except _RECOVERABLE_WAYLAND_EXCEPTIONS:
                pass
            self._display = None


def create_wayland_idle_tracker(
    timeout_ms: int = 10_000,
    display_name_or_fd: int | str | None = None,
) -> Optional[WaylandIdleTracker]:
    try:
        return WaylandIdleTracker(timeout_ms=timeout_ms, display_name_or_fd=display_name_or_fd)
    except _RECOVERABLE_WAYLAND_EXCEPTIONS as exc:
        logger.info("Wayland idle tracker unavailable: %s", exc)
        return None
