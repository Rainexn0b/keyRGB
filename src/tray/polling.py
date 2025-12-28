"""Tray polling entrypoints.

This module is kept for backwards compatibility; it delegates to the
implementation modules to keep each polling loop focused and easier to maintain.
"""

from __future__ import annotations

from .config_polling import start_config_polling
from .hardware_polling import start_hardware_polling
from .icon_color_polling import start_icon_color_polling

__all__ = [
    "start_config_polling",
    "start_hardware_polling",
    "start_icon_color_polling",
]
