from __future__ import annotations

import logging
import threading
import weakref
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger(__name__)


class _TransportLike(Protocol):
    """Minimal protocol for transports managed by SharedHidrawTransportManager."""

    _fd: int | None

    def send_feature_report(self, report: bytes) -> int: ...

    def close(self) -> None: ...


class HidrawTransportProxy:
    """Thread-safe proxy to a shared hidraw transport.

    Do not call ``close()`` on the underlying transport directly; use this
    proxy's ``close()`` method, which releases the shared reference. The
    manager only closes the underlying file descriptor when the last active
    reference is released.
    """

    def __init__(
        self,
        *,
        backend_name: str,
        manager: SharedHidrawTransportManager,
        proxy_id: int,
    ) -> None:
        self.backend_name = str(backend_name)
        self._manager_ref = weakref.ref(manager)
        self._proxy_id = proxy_id

    def send_feature_report(self, report: bytes) -> int:
        manager = self._require_manager()
        return manager._send_feature_report(self.backend_name, self._proxy_id, bytes(report))

    def write_output_report(self, report: bytes) -> int | None:
        manager = self._require_manager()
        return manager._write_output_report(self.backend_name, self._proxy_id, bytes(report))

    @property
    def is_alive(self) -> bool:
        manager = self._manager_ref()
        if manager is None:
            return False
        return manager.is_alive(self.backend_name)

    def close(self) -> None:
        """Release the shared reference held by this proxy."""
        manager = self._manager_ref()
        if manager is None:
            return
        manager._release(self.backend_name, self._proxy_id)

    def _require_manager(self) -> SharedHidrawTransportManager:
        manager = self._manager_ref()
        if manager is None:
            raise RuntimeError("SharedHidrawTransportManager has been destroyed")
        return manager


@dataclass
class _TransportEntry:
    transport: _TransportLike
    ref_count: int = 0
    write_lock: threading.Lock = field(default_factory=threading.Lock)
    proxy_ids: set[int] = field(default_factory=set)


class SharedHidrawTransportManager:
    """Reference-counted, thread-safe shared hidraw transport manager.

    This manager opens one hidraw transport per ``backend_name`` and vends
    lightweight proxies to multiple consumers (e.g., keyboard + logo + neon +
    vent zone devices). The transport is closed only when the last active
    proxy is released or when the entry is explicitly invalidated.

    The manager is intentionally generic: the ``opener`` callable returns any
    object with ``send_feature_report`` and ``write_output_report`` methods,
    plus a ``close`` method. This keeps the manager usable for both
    ``HidrawFeatureOutputTransport`` and test doubles.
    """

    def __init__(self) -> None:
        self._state_lock = threading.RLock()
        self._entries: dict[str, _TransportEntry] = {}
        self._next_proxy_id = 0

    def acquire(
        self,
        backend_name: str,
        opener: Callable[[], _TransportLike],
    ) -> HidrawTransportProxy:
        """Acquire a proxy for *backend_name*, opening the transport if needed."""
        with self._state_lock:
            entry = self._entries.get(backend_name)
            if entry is None:
                transport = opener()
                entry = _TransportEntry(transport=transport)
                self._entries[backend_name] = entry

            proxy_id = self._next_proxy_id
            self._next_proxy_id += 1
            entry.ref_count += 1
            entry.proxy_ids.add(proxy_id)

            return HidrawTransportProxy(
                backend_name=backend_name,
                manager=self,
                proxy_id=proxy_id,
            )

    def _release(self, backend_name: str, proxy_id: int) -> None:
        with self._state_lock:
            entry = self._entries.get(backend_name)
            if entry is None:
                return
            if proxy_id not in entry.proxy_ids:
                return

            entry.proxy_ids.discard(proxy_id)
            entry.ref_count -= 1

            if entry.ref_count <= 0:
                self._close_entry(entry)
                self._entries.pop(backend_name, None)

    def invalidate(self, backend_name: str) -> None:
        """Forcibly close the transport for *backend_name* and drop all proxies."""
        with self._state_lock:
            entry = self._entries.pop(backend_name, None)
            if entry is not None:
                self._close_entry(entry)

    def is_alive(self, backend_name: str) -> bool:
        with self._state_lock:
            entry = self._entries.get(backend_name)
            if entry is None:
                return False
            return entry.transport._fd is not None

    def _send_feature_report(self, backend_name: str, proxy_id: int, report: bytes) -> int:
        with self._state_lock:
            entry = self._entries.get(backend_name)
            if entry is None or proxy_id not in entry.proxy_ids:
                raise RuntimeError("hidraw transport proxy is no longer valid")
            transport = entry.transport
            write_lock = entry.write_lock

        with write_lock:
            try:
                return int(transport.send_feature_report(report))
            except OSError:
                self.invalidate(backend_name)
                raise

    def _write_output_report(self, backend_name: str, proxy_id: int, report: bytes) -> int | None:
        with self._state_lock:
            entry = self._entries.get(backend_name)
            if entry is None or proxy_id not in entry.proxy_ids:
                raise RuntimeError("hidraw transport proxy is no longer valid")
            transport = entry.transport
            write_lock = entry.write_lock
            write_fn = getattr(transport, "write_output_report", None)
            if write_fn is None:
                return None

        with write_lock:
            try:
                return int(write_fn(report))
            except OSError:
                self.invalidate(backend_name)
                raise

    @staticmethod
    def _close_entry(entry: _TransportEntry) -> None:
        try:
            close_fn = getattr(entry.transport, "close", None)
            if callable(close_fn):
                close_fn()
        except (OSError, RuntimeError, ValueError):
            logger.debug("Error closing shared hidraw transport", exc_info=True)

    def __del__(self) -> None:
        try:
            with self._state_lock:
                entries = list(self._entries.items())
                self._entries.clear()
            for _backend_name, entry in entries:
                self._close_entry(entry)
        except (OSError, RuntimeError, TypeError, ValueError):
            logger.debug("Ignoring shared transport manager cleanup failure", exc_info=True)
