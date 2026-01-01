"""Tray lifecycle helpers.

This module contains small orchestration helpers used by the tray app during
startup. They are intentionally defensive: the tray should remain robust even
if optional features fail.
"""

from __future__ import annotations

from typing import Any

from .pollers.config_polling import start_config_polling
from .pollers.hardware_polling import start_hardware_polling
from .pollers.icon_color_polling import start_icon_color_polling
from .pollers.idle_power_polling import start_idle_power_polling


def start_power_monitoring(tray: Any, *, power_manager_cls: type[Any], config: Any) -> Any:
    """Create and start the PowerManager monitoring loop.

    Returns the created PowerManager instance.
    """

    power_manager = power_manager_cls(tray, config=config)
    power_manager.start_monitoring()
    return power_manager


def start_all_polling(tray: Any, *, ite_num_rows: int, ite_num_cols: int) -> None:
    """Start all pollers used by the tray UI."""

    start_hardware_polling(tray)
    start_config_polling(tray, ite_num_rows=ite_num_rows, ite_num_cols=ite_num_cols)
    start_icon_color_polling(tray)
    start_idle_power_polling(tray, ite_num_rows=ite_num_rows, ite_num_cols=ite_num_cols)


def maybe_autostart_effect(tray: Any) -> None:
    """Start the current effect if config requests autostart.

    Assumes the tray has `config`, `is_off`, and `_start_current_effect`.
    """

    if getattr(tray.config, "autostart", False) and not tray.is_off:
        tray._start_current_effect()
