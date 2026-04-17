"""Tray lifecycle helpers.

This module contains small orchestration helpers used by the tray app during
startup. They are intentionally defensive: the tray should remain robust even
if optional features fail.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, TypeVar

from ..pollers.config_polling import start_config_polling
from ..pollers.hardware_polling import start_hardware_polling
from ..pollers.icon_color_polling import start_icon_color_polling
from ..pollers.idle_power import start_idle_power_polling
from ..protocols import ConfigPollingTrayProtocol, IdlePowerTrayProtocol

if TYPE_CHECKING:
    from src.core.config import Config


class _MonitoringPowerManager(Protocol):
    def start_monitoring(self) -> None: ...


_PowerManagerT = TypeVar("_PowerManagerT", bound=_MonitoringPowerManager, covariant=True)
_TrayT = TypeVar("_TrayT", contravariant=True)


class _PowerManagerFactory(Protocol[_TrayT, _PowerManagerT]):
    def __call__(self, tray: _TrayT, *, config: Config | None = None) -> _PowerManagerT: ...


class _IconColorPollingTray(Protocol):
    config: Config
    backend: object | None
    is_off: bool

    def _update_icon(self, *, animate: bool = True) -> None: ...

    def _log_exception(self, msg: str, exc: Exception) -> None: ...


class _LifecyclePollingTray(
    ConfigPollingTrayProtocol,
    IdlePowerTrayProtocol,
    _IconColorPollingTray,
    Protocol,
):
    """Combined tray surface required during lifecycle startup."""


class _AutostartEffectTray(Protocol):
    config: object
    is_off: bool

    def _start_current_effect(self, **kwargs: object) -> None: ...


def start_power_monitoring(
    tray: _TrayT,
    *,
    power_manager_cls: _PowerManagerFactory[_TrayT, _PowerManagerT],
    config: Config | None,
) -> _PowerManagerT:
    """Create and start the PowerManager monitoring loop.

    Returns the created PowerManager instance.
    """

    power_manager = power_manager_cls(tray, config=config)
    power_manager.start_monitoring()
    return power_manager


def start_all_polling(tray: _LifecyclePollingTray, *, ite_num_rows: int, ite_num_cols: int) -> None:
    """Start all pollers used by the tray UI."""

    start_hardware_polling(tray)
    start_config_polling(tray, ite_num_rows=ite_num_rows, ite_num_cols=ite_num_cols)
    start_icon_color_polling(tray)
    start_idle_power_polling(tray, ite_num_rows=ite_num_rows, ite_num_cols=ite_num_cols)


def maybe_autostart_effect(tray: _AutostartEffectTray) -> None:
    """Start the current effect if config requests autostart.

    Assumes the tray has `config`, `is_off`, and `_start_current_effect`.
    """

    if getattr(tray.config, "autostart", False) and not tray.is_off:
        tray._start_current_effect()
