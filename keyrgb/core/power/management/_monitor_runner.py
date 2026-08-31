"""Power-monitor orchestration helpers for PowerManager."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Protocol

logger = logging.getLogger(__name__)

# Bounded restart/backoff for the primary login1 (dbus-monitor) suspend/resume
# monitor. These bounds exist so a monitor that exits while the manager still
# wants monitoring (EOF, child exit, or a recoverable callback exception) is
# retried without busy-looping during repeated failure or shutdown.
_MONITOR_RESTART_INITIAL_DELAY_S = 1.0
_MONITOR_RESTART_MAX_DELAY_S = 30.0
_MONITOR_RESTART_BACKOFF_FACTOR = 2.0
_MONITOR_STABLE_RUN_THRESHOLD_S = 5.0
_MONITOR_SHUTDOWN_POLL_INTERVAL_S = 0.5


def _interruptible_sleep(
    duration_s: float,
    is_running: Callable[[], bool],
    *,
    interval_s: float = _MONITOR_SHUTDOWN_POLL_INTERVAL_S,
) -> None:
    """Sleep for ``duration_s`` but return early if ``is_running`` becomes false.

    Used during restart backoff so a shutdown request is honored promptly
    instead of blocking for the full backoff window.
    """

    remaining = float(duration_s)
    while remaining > 0 and is_running():
        step = min(interval_s, remaining)
        time.sleep(step)
        remaining -= step


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
    """Run the primary login1 monitor with restart and ACPI fallback.

    The login1 monitor is a single long-running ``dbus-monitor`` invocation that
    ends on EOF, child exit, or a raised exception. None of those conditions must
    silently terminate suspend/resume monitoring while ``manager.monitoring`` is
    still true, so a clean (non-shutdown) exit is retried with bounded exponential
    backoff. ``FileNotFoundError`` (dbus-monitor absent) is a stable condition and
    fails over to the ACPI lid monitor exactly once.

    Lid monitoring is started at most once across all monitor invocations: a
    restart spawns a fresh ``dbus-monitor`` but the already-running lid thread
    keeps owning lid callbacks, so re-invoking the lid starter would duplicate
    them.
    """

    lid_started = False

    def _on_started_once() -> None:
        nonlocal lid_started
        if lid_started:
            logger.debug("Lid monitor already started; skipping duplicate start on monitor restart")
            return
        start_lid_monitor_fn()
        # Mark started only after a successful start so a transient failure is
        # retried on the next monitor restart instead of being permanently skipped.
        lid_started = True

    logger.info("Power monitoring started using dbus-monitor")

    retry_delay_s = _MONITOR_RESTART_INITIAL_DELAY_S
    consecutive_failures = 0

    while manager.monitoring:
        run_start = time.monotonic()
        try:
            monitor_prepare_for_sleep_fn(
                is_running=lambda: manager.monitoring,
                on_started=_on_started_once,
                on_suspend=manager._on_suspend,
                on_resume=manager._on_resume,
                on_process_started=manager._register_monitor_process,
                on_process_stopped=manager._unregister_monitor_process,
            )
        except FileNotFoundError:
            logger.warning("dbus-monitor not available, trying alternative method")
            monitor_acpi_events_fn()
            return
        except monitor_errors as exc:  # @quality-exception exception-transparency: login1 monitoring is an external runtime boundary and power monitoring must remain available on recoverable runtime failures
            if not manager.monitoring:
                logger.info("Power monitoring stopping after recoverable error")
                return
            consecutive_failures += 1
            logger.exception(
                "Power monitoring recovered from %s after recoverable error; restarting in %.1fs (attempt %d)",
                type(exc).__name__,
                retry_delay_s,
                consecutive_failures,
            )
            _interruptible_sleep(retry_delay_s, lambda: manager.monitoring)
            if not manager.monitoring:
                logger.info("Power monitoring stopping during restart backoff")
                return
            retry_delay_s = min(retry_delay_s * _MONITOR_RESTART_BACKOFF_FACTOR, _MONITOR_RESTART_MAX_DELAY_S)
            continue
        else:
            if not manager.monitoring:
                logger.info("Power monitoring stopped cleanly during dbus-monitor run")
                return
            run_duration = time.monotonic() - run_start
            # dbus-monitor ended (EOF or child exit) while the manager still
            # wants monitoring: restart it. A run that lasted long enough is
            # treated as stable and resets the backoff so a later transient exit
            # is not penalized indefinitely.
            if run_duration >= _MONITOR_STABLE_RUN_THRESHOLD_S:
                consecutive_failures = 0
                retry_delay_s = _MONITOR_RESTART_INITIAL_DELAY_S
            else:
                consecutive_failures += 1
            logger.warning(
                "dbus-monitor ended unexpectedly (EOF or process exit); restarting in %.1fs (attempt %d)",
                retry_delay_s,
                consecutive_failures,
            )
            _interruptible_sleep(retry_delay_s, lambda: manager.monitoring)
            if not manager.monitoring:
                logger.info("Power monitoring stopping during restart backoff")
                return
            retry_delay_s = min(retry_delay_s * _MONITOR_RESTART_BACKOFF_FACTOR, _MONITOR_RESTART_MAX_DELAY_S)
            continue


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
