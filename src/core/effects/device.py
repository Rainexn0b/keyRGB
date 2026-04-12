from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterable, Mapping, Sized
from threading import RLock
from typing import Protocol, cast

from src.core.backends.registry import select_backend
from src.core.utils.logging_utils import log_throttled


_LOG_COLOR_SNAPSHOT_ERRORS = (
    AttributeError,
    IndexError,
    KeyError,
    LookupError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_LOG_LENGTH_SNAPSHOT_ERRORS = (
    AttributeError,
    KeyError,
    LookupError,
    OSError,
    OverflowError,
    RuntimeError,
    TypeError,
    ValueError,
)
_KEYBOARD_ACQUIRE_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)

Color = tuple[int, int, int]
PerKeyColorMap = Mapping[tuple[int, int], Color]


class KeyboardDeviceProtocol(Protocol):
    def turn_off(self) -> None: ...

    def set_brightness(self, brightness: int) -> None: ...

    def set_color(self, color: object, *, brightness: int) -> object: ...

    def set_key_colors(
        self,
        color_map: object,
        *,
        brightness: int,
        enable_user_mode: bool = True,
    ) -> object: ...

    def set_effect(self, effect_data: object) -> None: ...

    def set_palette_color(self, slot: int, color: object) -> None: ...

    def get_brightness(self) -> int: ...

    def is_off(self) -> bool: ...


class KeyboardBackendProtocol(Protocol):
    def get_device(self) -> KeyboardDeviceProtocol: ...


class NullKeyboard:
    """Fallback keyboard implementation used when no device is available."""

    def turn_off(self) -> None:
        return

    def set_brightness(self, _brightness: int) -> None:
        return

    def set_color(self, _color: object, *, brightness: int) -> None:
        return

    def set_key_colors(
        self,
        _color_map: object,
        *,
        brightness: int,
        enable_user_mode: bool = True,
    ) -> None:
        return

    def set_effect(self, _effect_data: object) -> None:
        return

    def set_palette_color(self, _slot: int, _color: object) -> None:
        return

    def get_brightness(self) -> int:
        return 0

    def is_off(self) -> bool:
        return True


def _debug_brightness_enabled() -> bool:
    return os.environ.get("KEYRGB_DEBUG_BRIGHTNESS") == "1"


def get_keyboard_device(
    *,
    backend: KeyboardBackendProtocol | None = None,
) -> KeyboardDeviceProtocol:
    """Return the keyboard device for the selected backend.

    When a backend is injected explicitly, use it directly. Otherwise, fall
    back to backend auto-selection.
    """

    selected_backend = backend if backend is not None else select_backend()
    if selected_backend is None:
        raise FileNotFoundError("No keyboard backend available")
    return cast(KeyboardDeviceProtocol, selected_backend.get_device())


def get(*, backend: KeyboardBackendProtocol | None = None) -> KeyboardDeviceProtocol:
    """Compatibility alias for legacy callers and tests."""

    return get_keyboard_device(backend=backend)


def _rgb_for_debug_log(color: object) -> tuple[object, object, object]:
    if not isinstance(color, Iterable):
        return ("?", "?", "?")

    try:
        snapshot = tuple(color)
    except _LOG_COLOR_SNAPSHOT_ERRORS:
        return ("?", "?", "?")

    if len(snapshot) != 3:
        return ("?", "?", "?")

    return snapshot[0], snapshot[1], snapshot[2]


def _size_for_debug_log(value: object) -> int:
    if not isinstance(value, Sized):
        return -1

    try:
        return len(value)
    except _LOG_LENGTH_SNAPSHOT_ERRORS:
        return -1


class _BrightnessLoggingKeyboardProxy:
    """Proxy wrapper that logs brightness-related device calls.

    Enabled only when `KEYRGB_DEBUG_BRIGHTNESS=1`.
    """

    def __init__(self, inner: KeyboardDeviceProtocol, *, logger: logging.Logger):
        self._inner = inner
        self._logger = logger

    def __getattr__(self, name: str) -> object:
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

    def set_color(self, color: object, *, brightness: int) -> object:
        if _debug_brightness_enabled():
            r, g, b = _rgb_for_debug_log(color)
            self._logger.info(
                "kb.set_color rgb=(%s,%s,%s) brightness=%s (t=%.6f)",
                r,
                g,
                b,
                int(brightness),
                float(time.monotonic()),
            )
        return self._inner.set_color(color, brightness=int(brightness))

    def set_key_colors(
        self,
        color_map: object,
        *,
        brightness: int,
        enable_user_mode: bool = True,
    ) -> object:
        if _debug_brightness_enabled():
            self._logger.info(
                "kb.set_key_colors keys=%s brightness=%s enable_user_mode=%s (t=%.6f)",
                _size_for_debug_log(color_map),
                int(brightness),
                bool(enable_user_mode),
                float(time.monotonic()),
            )
        return self._inner.set_key_colors(
            color_map,
            brightness=int(brightness),
            enable_user_mode=bool(enable_user_mode),
        )

    def set_effect(self, effect_data: object) -> None:
        if _debug_brightness_enabled():
            self._logger.info(
                "kb.set_effect bytes=%s (t=%.6f)",
                _size_for_debug_log(effect_data),
                float(time.monotonic()),
            )
        return self._inner.set_effect(effect_data)

    def set_palette_color(self, slot: int, color: object) -> None:
        if _debug_brightness_enabled():
            r, g, b = _rgb_for_debug_log(color)
            self._logger.info(
                "kb.set_palette_color slot=%s rgb=(%s,%s,%s) (t=%.6f)",
                int(slot),
                r,
                g,
                b,
                float(time.monotonic()),
            )
        return self._inner.set_palette_color(int(slot), color)


def acquire_keyboard(
    *,
    kb_lock: RLock,
    logger: logging.Logger,
    backend: KeyboardBackendProtocol | None = None,
) -> tuple[KeyboardDeviceProtocol, bool]:
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
            kb = get() if backend is None else get(backend=backend)
        if _debug_brightness_enabled() and not isinstance(kb, NullKeyboard):
            kb = _BrightnessLoggingKeyboardProxy(kb, logger=logger)
        return kb, True
    except FileNotFoundError:
        return NullKeyboard(), False
    except _KEYBOARD_ACQUIRE_RUNTIME_ERRORS as exc:  # @quality-exception exception-transparency: device acquisition crosses backend probing and hardware startup boundaries; recoverable failures are non-fatal for effect startup
        log_throttled(
            logger,
            "effects.acquire_keyboard",
            interval_s=60,
            level=logging.DEBUG,
            msg="Failed to acquire keyboard device; falling back to NullKeyboard",
            exc=exc,
        )
        return NullKeyboard(), False
