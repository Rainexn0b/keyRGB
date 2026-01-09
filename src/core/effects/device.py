from __future__ import annotations

import logging
import os
import time
from threading import RLock
from typing import Any, Tuple

from src.core.effects.ite_backend import get
from src.core.utils.logging_utils import log_throttled


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


def _debug_brightness_enabled() -> bool:
    return os.environ.get("KEYRGB_DEBUG_BRIGHTNESS") == "1"


class _BrightnessLoggingKeyboardProxy:
    """Proxy wrapper that logs brightness-related device calls.

    Enabled only when `KEYRGB_DEBUG_BRIGHTNESS=1`.
    """

    def __init__(self, inner: Any, *, logger: logging.Logger):
        self._inner = inner
        self._logger = logger

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def set_brightness(self, brightness: int) -> None:
        if _debug_brightness_enabled():
            self._logger.info(
                "kb.set_brightness: %s (t=%.6f)",
                int(brightness),
                float(time.monotonic()),
            )
        return self._inner.set_brightness(int(brightness))

    def get_brightness(self) -> int:
        v = int(self._inner.get_brightness())
        if _debug_brightness_enabled():
            self._logger.info(
                "kb.get_brightness -> %s (t=%.6f)",
                v,
                float(time.monotonic()),
            )
        return v

    def turn_off(self) -> None:
        if _debug_brightness_enabled():
            self._logger.info("kb.turn_off (t=%.6f)", float(time.monotonic()))
        return self._inner.turn_off()

    def is_off(self) -> bool:
        v = bool(self._inner.is_off())
        if _debug_brightness_enabled():
            self._logger.info(
                "kb.is_off -> %s (t=%.6f)",
                v,
                float(time.monotonic()),
            )
        return v

    def set_color(self, color, *, brightness: int):
        if _debug_brightness_enabled():
            try:
                r, g, b = color
            except Exception:
                r, g, b = ("?", "?", "?")
            self._logger.info(
                "kb.set_color rgb=(%s,%s,%s) brightness=%s (t=%.6f)",
                r,
                g,
                b,
                int(brightness),
                float(time.monotonic()),
            )
        return self._inner.set_color(color, brightness=int(brightness))

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True):
        if _debug_brightness_enabled():
            try:
                n = len(color_map)
            except Exception:
                n = -1
            self._logger.info(
                "kb.set_key_colors keys=%s brightness=%s enable_user_mode=%s (t=%.6f)",
                n,
                int(brightness),
                bool(enable_user_mode),
                float(time.monotonic()),
            )
        return self._inner.set_key_colors(
            color_map,
            brightness=int(brightness),
            enable_user_mode=bool(enable_user_mode),
        )

    def set_effect(self, effect_data) -> None:
        if _debug_brightness_enabled():
            try:
                size = len(effect_data)  # type: ignore[arg-type]
            except Exception:
                size = -1
            self._logger.info("kb.set_effect bytes=%s (t=%.6f)", size, float(time.monotonic()))
        return self._inner.set_effect(effect_data)

    def set_palette_color(self, slot: int, color) -> None:
        if _debug_brightness_enabled():
            try:
                r, g, b = color
            except Exception:
                r, g, b = ("?", "?", "?")
            self._logger.info(
                "kb.set_palette_color slot=%s rgb=(%s,%s,%s) (t=%.6f)",
                int(slot),
                r,
                g,
                b,
                float(time.monotonic()),
            )
        return self._inner.set_palette_color(int(slot), color)


def acquire_keyboard(*, kb_lock: RLock, logger: logging.Logger) -> Tuple[Any, bool]:
    """Best-effort attempt to acquire the keyboard device.

    Returns:
        (keyboard, device_available)

    Never raises.
    """

    # Safety: unit tests must not touch real hardware by default.
    # Allow opt-in for hardware tests via env var.
    allow_hardware = os.environ.get("KEYRGB_ALLOW_HARDWARE") == "1" or os.environ.get("KEYRGB_HW_TESTS") == "1"

    if os.environ.get("PYTEST_CURRENT_TEST") and not allow_hardware:
        return NullKeyboard(), False

    try:
        with kb_lock:
            kb = get()
        if _debug_brightness_enabled() and not isinstance(kb, NullKeyboard):
            kb = _BrightnessLoggingKeyboardProxy(kb, logger=logger)
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
