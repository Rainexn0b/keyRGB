from __future__ import annotations

import logging
import os
from threading import RLock
from typing import Any, Tuple

from src.core.effects.ite_backend import get
from src.core.logging_utils import log_throttled


class NullKeyboard:
    """Fallback keyboard implementation used when no device is available."""

    def turn_off(self) -> None:
        return

    def set_brightness(self, _brightness: int) -> None:
        return

    def set_color(self, _color, *, brightness: int):
        return

    def set_key_colors(self, _color_map, *, brightness: int, enable_user_mode: bool = True):
        return

    def set_effect(self, _effect_data) -> None:
        return

    def set_palette_color(self, _slot: int, _color) -> None:
        return

    def get_brightness(self) -> int:
        return 0

    def is_off(self) -> bool:
        return True


def acquire_keyboard(*, kb_lock: RLock, logger: logging.Logger) -> Tuple[Any, bool]:
    """Best-effort attempt to acquire the keyboard device.

    Returns:
        (keyboard, device_available)

    Never raises.
    """

    # Safety: unit tests must not touch real hardware by default.
    # Allow opt-in for hardware tests via env var.
    if os.environ.get("PYTEST_CURRENT_TEST") and os.environ.get("KEYRGB_ALLOW_HARDWARE") != "1":
        return NullKeyboard(), False

    try:
        with kb_lock:
            kb = get()
        return kb, True
    except FileNotFoundError:
        return NullKeyboard(), False
    except Exception as exc:
        log_throttled(
            logger,
            "effects.acquire_keyboard",
            interval_s=60,
            level=logging.DEBUG,
            msg="Failed to acquire keyboard device; falling back to NullKeyboard",
            exc=exc,
        )
        return NullKeyboard(), False
