"""Tray lifecycle helpers.

This module contains small orchestration helpers used by the tray app during
startup. They are intentionally defensive: the tray should remain robust even
if optional features fail.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any, Protocol, TypeVar, cast

from ..controllers.runtime_coordination import run_tray_transition
from ..pollers.config_polling import start_config_polling
from ..pollers.hardware_polling import start_hardware_polling
from ..pollers.icon_color_polling import start_icon_color_polling
from ..pollers.idle_power import start_idle_power_polling
from ..pollers.time_scheduler import start_time_scheduler_polling
from ..protocols import ConfigPollingTrayProtocol, IdlePowerTrayProtocol, LightingTrayProtocol

logger = logging.getLogger(__name__)

_SHUTDOWN_RECOVERABLE_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)

if TYPE_CHECKING:
    from src.core.config import Config


class _MonitoringPowerManager(Protocol):
    def start_monitoring(self) -> None: ...

    def stop_monitoring(self) -> bool | None: ...


_PowerManagerT_co = TypeVar("_PowerManagerT_co", bound=_MonitoringPowerManager, covariant=True)
_TrayT_contra = TypeVar("_TrayT_contra", contravariant=True)


class _PowerManagerFactory(Protocol[_TrayT_contra, _PowerManagerT_co]):
    def __call__(self, tray: _TrayT_contra, *, config: Config | None = None) -> _PowerManagerT_co: ...


class _IconColorPollingTray(Protocol):
    config: Config
    backend: object | None
    is_off: bool

    def _update_icon(self, *, animate: bool = True) -> None: ...

    def _log_exception(self, msg: str, exc: Exception) -> None: ...


class _LifecyclePollingTray(
    ConfigPollingTrayProtocol,
    IdlePowerTrayProtocol,
    LightingTrayProtocol,
    _IconColorPollingTray,
    Protocol,
):
    """Combined tray surface required during lifecycle startup."""

    power_manager: object | None


class _AutostartEffectTray(Protocol):
    config: object
    is_off: bool

    def _start_current_effect(self, **kwargs: object) -> bool | None: ...


def start_power_monitoring(
    tray: _TrayT_contra,
    *,
    power_manager_cls: _PowerManagerFactory[_TrayT_contra, _PowerManagerT_co],
    config: Config | None,
) -> _PowerManagerT_co:
    """Create and start the PowerManager monitoring loop.

    Returns the created PowerManager instance.
    """

    power_manager = power_manager_cls(tray, config=config)
    monitoring_started = False
    try:
        prime_power_source = getattr(power_manager, "prime_power_source_state", None)
        if callable(prime_power_source):
            prime_power_source()
        power_manager.start_monitoring()
        monitoring_started = True
    finally:
        if not monitoring_started:
            try:
                power_manager.stop_monitoring()
            except _SHUTDOWN_RECOVERABLE_ERRORS:
                logger.debug("Failed to roll back partial power monitoring startup", exc_info=True)
    return power_manager


def _record_polling_thread(tray: object, thread: object | None) -> None:
    if thread is None:
        return
    threads = vars(tray).get("_polling_threads")
    if not isinstance(threads, list):
        threads = []
        vars(tray)["_polling_threads"] = threads
    threads.append(thread)


def start_all_polling(tray: _LifecyclePollingTray, *, ite_num_rows: int, ite_num_cols: int) -> None:
    """Start all pollers used by the tray UI."""

    shutdown_event = threading.Event()
    vars(tray)["_polling_shutdown_event"] = shutdown_event
    vars(tray)["_polling_threads"] = []

    _record_polling_thread(tray, start_hardware_polling(tray))
    _record_polling_thread(tray, start_config_polling(tray, ite_num_rows=ite_num_rows, ite_num_cols=ite_num_cols))
    _record_polling_thread(tray, start_icon_color_polling(tray))
    _record_polling_thread(
        tray,
        start_idle_power_polling(tray, ite_num_rows=ite_num_rows, ite_num_cols=ite_num_cols),
    )
    _record_polling_thread(tray, start_time_scheduler_polling(tray))


def stop_all_polling(tray: object, *, join_timeout_s: float = 2.0) -> bool:
    """Signal and join every poller, returning whether all workers stopped."""

    event = vars(tray).get("_polling_shutdown_event")
    set_event = getattr(event, "set", None)
    if callable(set_event):
        set_event()

    threads = vars(tray).get("_polling_threads")
    if not isinstance(threads, list):
        return True
    unquiesced_threads: list[object] = []
    for thread in tuple(threads):
        join = getattr(thread, "join", None)
        if not callable(join):
            unquiesced_threads.append(thread)
            continue
        try:
            join(timeout=max(0.0, float(join_timeout_s)))
        except (RuntimeError, TypeError):
            unquiesced_threads.append(thread)
            logger.debug("Failed to join tray polling thread during shutdown", exc_info=True)
            continue

        is_alive = getattr(thread, "is_alive", None)
        if not callable(is_alive):
            unquiesced_threads.append(thread)
            continue
        try:
            if bool(is_alive()):
                unquiesced_threads.append(thread)
        except _SHUTDOWN_RECOVERABLE_ERRORS:
            unquiesced_threads.append(thread)
            logger.debug("Failed to verify tray polling thread shutdown", exc_info=True)

    threads[:] = unquiesced_threads
    if unquiesced_threads:
        logger.warning(
            "Tray shutdown still has %d active or unverifiable polling worker(s)",
            len(unquiesced_threads),
        )
    return not unquiesced_threads


def shutdown_tray_runtime_best_effort(tray: object) -> None:
    """Quiesce runtime producers and release devices in safe order."""

    producers_quiesced = True
    try:
        producers_quiesced = stop_all_polling(tray)
    except _SHUTDOWN_RECOVERABLE_ERRORS:
        producers_quiesced = False
        logger.debug("Failed to stop tray pollers during shutdown", exc_info=True)

    power_manager = getattr(tray, "power_manager", None)
    stop_monitoring = getattr(power_manager, "stop_monitoring", None)
    if callable(stop_monitoring):
        try:
            if stop_monitoring() is False:
                producers_quiesced = False
        except _SHUTDOWN_RECOVERABLE_ERRORS:
            producers_quiesced = False
            logger.debug("Failed to stop power monitoring during shutdown", exc_info=True)

    if not producers_quiesced:
        logger.warning("Skipping effects engine teardown because runtime producers are still active")
        return

    coordinator = getattr(tray, "runtime_coordinator", None)
    stop_and_drain = getattr(coordinator, "stop_and_drain", None)
    if callable(stop_and_drain):
        try:
            if stop_and_drain(timeout_s=2.0) is False:
                logger.warning("Skipping effects engine teardown because the runtime coordinator is still active")
                return
        except _SHUTDOWN_RECOVERABLE_ERRORS:
            logger.debug("Failed to stop tray runtime coordinator during shutdown", exc_info=True)
            return

    engine = getattr(tray, "engine", None)
    engine_close = getattr(engine, "close", None)
    if not callable(engine_close):
        engine_close = getattr(engine, "stop", None)
    engine_quiesced = True
    if callable(engine_close):
        try:
            engine_close()
        except _SHUTDOWN_RECOVERABLE_ERRORS:
            engine_quiesced = False
            logger.debug("Failed to close effects engine during shutdown", exc_info=True)

    engine_thread = getattr(engine, "thread", None)
    thread_is_alive = getattr(engine_thread, "is_alive", None)
    if callable(thread_is_alive):
        try:
            engine_quiesced = engine_quiesced and not bool(thread_is_alive())
        except _SHUTDOWN_RECOVERABLE_ERRORS:
            engine_quiesced = False
            logger.debug("Failed to verify effects engine shutdown", exc_info=True)

    if not engine_quiesced:
        logger.warning("Skipping secondary target close because the effects engine is still active")
        return

    try:
        from src.tray.controllers.software_target_controller import close_secondary_software_target_cache

        close_secondary_software_target_cache(cast(Any, tray))
    except _SHUTDOWN_RECOVERABLE_ERRORS:
        logger.debug("Failed to close secondary target cache during shutdown", exc_info=True)


def maybe_autostart_effect(tray: _AutostartEffectTray) -> None:
    """Start the current effect if config requests autostart.

    Assumes the tray has `config`, `is_off`, and `_start_current_effect`.
    """

    def autostart_transition() -> None:
        if getattr(tray.config, "autostart", False) and not tray.is_off:
            tray._start_current_effect()

    run_tray_transition(tray, autostart_transition)
