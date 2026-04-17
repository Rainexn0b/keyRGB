"""Power-monitor orchestration helpers for PowerManager."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol


class _JoinableThreadProtocol(Protocol):
    def start(self) -> None: ...

    def join(self, timeout: float | None = None) -> None: ...


class _ThreadFactoryProtocol(Protocol):
    def __call__(self, *, target: Callable[[], None], daemon: bool) -> _JoinableThreadProtocol: ...


class _PowerMonitorManagerProtocol(Protocol):
    monitoring: bool
    monitor_thread: _JoinableThreadProtocol | None
    _battery_thread: _JoinableThreadProtocol | None

    def _monitor_loop(self) -> None: ...

    def _battery_saver_loop(self) -> None: ...

    def _on_suspend(self) -> None: ...

    def _on_resume(self) -> None: ...

    def _on_lid_close(self) -> None: ...

    def _on_lid_open(self) -> None: ...


class _PrepareForSleepMonitorProtocol(Protocol):
    def __call__(
        self,
        *,
        is_running: Callable[[], bool],
        on_suspend: Callable[[], None],
        on_resume: Callable[[], None],
        on_started: Callable[[], None] | None = None,
    ) -> None: ...


class _LidEventMonitorProtocol(Protocol):
    def __call__(
        self,
        *,
        is_running: Callable[[], bool],
        on_lid_close: Callable[[], None],
        on_lid_open: Callable[[], None],
        logger: logging.Logger,
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


def stop_monitoring(manager: _PowerMonitorManagerProtocol, *, join_timeout_s: int) -> None:
    """Stop monitoring and join worker threads best-effort."""

    manager.monitoring = False
    if manager.monitor_thread:
        manager.monitor_thread.join(timeout=join_timeout_s)
    if manager._battery_thread:
        manager._battery_thread.join(timeout=join_timeout_s)


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

    start_sysfs_lid_monitoring_fn(
        is_running=lambda: manager.monitoring,
        on_lid_close=manager._on_lid_close,
        on_lid_open=manager._on_lid_open,
        logger=logger,
    )


def run_acpi_monitoring(
    manager: _PowerMonitorManagerProtocol,
    *,
    logger: logging.Logger,
    monitor_acpi_events_fn: _LidEventMonitorProtocol,
) -> None:
    """Run ACPI lid monitoring with the manager callbacks."""

    monitor_acpi_events_fn(
        is_running=lambda: manager.monitoring,
        on_lid_close=manager._on_lid_close,
        on_lid_open=manager._on_lid_open,
        logger=logger,
    )
