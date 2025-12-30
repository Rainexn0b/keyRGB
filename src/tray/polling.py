"""Tray polling entrypoints.

This module is kept for backwards compatibility; it delegates to the
implementation modules to keep each polling loop focused and easier to maintain.
"""

from __future__ import annotations

from .config_polling import start_config_polling
from .hardware_polling import start_hardware_polling
from .icon_color_polling import start_icon_color_polling


def start_all_polling(tray, *, ite_num_rows: int, ite_num_cols: int) -> None:
    """Start all background polling loops used by the tray.

    This is a small convenience wrapper to keep `KeyRGBTray.__init__` focused.
    """

    start_hardware_polling(tray)
    start_config_polling(tray, ite_num_rows=ite_num_rows, ite_num_cols=ite_num_cols)
    start_icon_color_polling(tray)

__all__ = [
    "start_config_polling",
    "start_hardware_polling",
    "start_icon_color_polling",
    "start_all_polling",
]
