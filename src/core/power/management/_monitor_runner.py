"""Power-monitor orchestration helpers for PowerManager."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

logger = logging.getLogger(__name__)


class _JoinableThreadProtocol(Protocol):
    def start(self) -> None: ...

    def join(self, timeout: float | None = None) -> None: ...

    def is_alive(self) -> bool: ...


class _ThreadFactoryProtocol(Protocol):
    def __call__(self, *, target: Callable[[], None], daemon: bool) -> _JoinableThreadProtocol: ...


class _PowerMonitorManagerProtocol(Protocol):
    monitoring: bool
    monitor_thread: _JoinableThreadProtocol | None
    _battery_thread: _JoinableThreadProtocol | None
    _lid_thread: _JoinableThreadProtocol | None

    def _monitor_loop(self) -> None: ...

    def _battery_saver_loop(self) -> None: ...

    def _on_suspend(self) -> None: ...

    def _on_resume(self) -> None: ...

    def _on_lid_close(self) -> None: ...

    def _on_lid_open(self) -> None: ...

    def _register_monitor_process(self, process: object) -> None: ...

    def _unregister_monitor_process(self, process: object) -> None: ...

    def _terminate_monitor_process(self) -> None: ...


class _PowerMonitorStopManagerProtocol(Protocol):
    monitoring: bool

    @property
    def monitor_thread(self) -> _JoinableThreadProtocol | None: ...

    @property
    def _battery_thread(self) -> _JoinableThreadProtocol | None: ...

    @property
    def _lid_thread(self) -> _JoinableThreadProtocol | None: ...

    def _terminate_monitor_process(self) -> None: ...


class _PrepareForSleepMonitorProtocol(Protocol):
    def __call__(
        self,
        *,
        is_running: Callable[[], bool],
        on_suspend: Callable[[], None],
        on_resume: Callable[[], None],
        on_started: Callable[[], None] | None = None,
        on_process_started: Callable[[object], None] | None = None,
        on_process_stopped: Callable[[object], None] | None = None,
    ) -> None: ...


class _LidEventMonitorProtocol(Protocol):
    def __call__(
        self,
        *,
        is_running: Callable[[], bool],
        on_lid_close: Callable[[], None],
        on_lid_open: Callable[[], None],
        logger: logging.Logger,
    ) -> _JoinableThreadProtocol: ...


class _AcpiEventMonitorProtocol(Protocol):
    def __call__(
        self,
        *,
        is_running: Callable[[], bool],
        on_lid_close: Callable[[], None],
        on_lid_open: Callable[[], None],
        logger: logging.Logger,
        on_process_started: Callable[[object], None] | None = None,
        on_process_stopped: Callable[[object], None] | None = None,
    ) -> None: ...


def start_monitoring(manager: _PowerMonitorManagerProtocol, *, thread_factory: _ThreadFactoryProtocol) -> None:
    """Start the monitor and battery-saver threads if they are not running."""

    if manager.monitoring:
        return

    manager.monitoring = True
    manager.monitor_thread = thread_factory(target=manager._monitor_loop, daemon=True)
    manager.monitor_thread.start()

    manager._battery_thread = thread_factory(target=manager._battery_saver_loop, daemon=True)
    manager._battery_thread.start()


def _join_monitor_thread(thread: _JoinableThreadProtocol | None, *, timeout_s: int) -> bool:
    """Join one monitor worker and report whether it is confirmed stopped."""

    if thread is None:
        return True
    try:
        thread.join(timeout=timeout_s)
    except (RuntimeError, TypeError):
        logger.debug("Failed to join power-monitor worker during shutdown", exc_info=True)
        return False
    try:
        return not bool(thread.is_alive())
    except (AttributeError, RuntimeError, TypeError):
        logger.debug("Failed to verify power-monitor worker shutdown", exc_info=True)
        return False


def stop_monitoring(manager: _PowerMonitorStopManagerProtocol, *, join_timeout_s: int) -> bool:
    """Stop monitoring and report whether every worker is quiescent."""

    manager.monitoring = False
    manager._terminate_monitor_process()
    worker_states = (
        _join_monitor_thread(manager.monitor_thread, timeout_s=join_timeout_s),
        _join_monitor_thread(manager._lid_thread, timeout_s=join_timeout_s),
        _join_monitor_thread(manager._battery_thread, timeout_s=join_timeout_s),
    )
    quiesced = all(worker_states)
    if not quiesced:
        logger.warning("Power monitoring workers remain active or unverifiable after shutdown")
    return quiesced


def run_monitor_loop(
    manager: _PowerMonitorManagerProtocol,
    *,
    logger: logging.Logger,
    monitor_prepare_for_sleep_fn: _PrepareForSleepMonitorProtocol,
    monitor_errors: tuple[type[BaseException], ...],
    start_lid_monitor_fn: Callable[[], None],
    monitor_acpi_events_fn: Callable[[], None],
) -> None:
    """Run the primary login1 monitor with ACPI fallback."""

    try:
        logger.info("Power monitoring started using dbus-monitor")

        monitor_prepare_for_sleep_fn(
            is_running=lambda: manager.monitoring,
            on_started=start_lid_monitor_fn,
            on_suspend=manager._on_suspend,
            on_resume=manager._on_resume,
            on_process_started=manager._register_monitor_process,
            on_process_stopped=manager._unregister_monitor_process,
        )

    except FileNotFoundError:
        logger.warning("dbus-monitor not available, trying alternative method")
        monitor_acpi_events_fn()
    except monitor_errors:  # @quality-exception exception-transparency: login1 monitoring is an external runtime boundary and power monitoring must remain available on recoverable runtime failures
        logger.exception("Power monitoring error")


def start_lid_monitoring(
    manager: _PowerMonitorManagerProtocol,
    *,
    logger: logging.Logger,
    start_sysfs_lid_monitoring_fn: _LidEventMonitorProtocol,
) -> None:
    """Start sysfs lid monitoring with the manager callbacks."""

    manager._lid_thread = start_sysfs_lid_monitoring_fn(
        is_running=lambda: manager.monitoring,
        on_lid_close=manager._on_lid_close,
        on_lid_open=manager._on_lid_open,
        logger=logger,
    )


def run_acpi_monitoring(
    manager: _PowerMonitorManagerProtocol,
    *,
    logger: logging.Logger,
    monitor_acpi_events_fn: _AcpiEventMonitorProtocol,
) -> None:
    """Run ACPI lid monitoring with the manager callbacks."""

    monitor_acpi_events_fn(
        is_running=lambda: manager.monitoring,
        on_lid_close=manager._on_lid_close,
        on_lid_open=manager._on_lid_open,
        logger=logger,
        on_process_started=manager._register_monitor_process,
        on_process_stopped=manager._unregister_monitor_process,
    )
