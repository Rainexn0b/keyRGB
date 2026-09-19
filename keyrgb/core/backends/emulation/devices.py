"""In-memory keyboard device parameterized by an emulated backend contract."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable, Mapping
from typing import Any, cast

from keyrgb.core.backends.base import BackendCapabilities
from keyrgb.core.config._lighting._coercion import normalize_precise_brightness_value

logger = logging.getLogger(__name__)

_COLOR_ERRORS = (TypeError, ValueError, OverflowError)
_MAP_ERRORS = (AttributeError, TypeError, ValueError)


def _debug_enabled() -> bool:
    return os.environ.get("KEYRGB_DEBUG") == "1"


def _clamp_channel(value: object) -> int:
    try:
        return max(0, min(255, int(cast(Any, value))))
    except _COLOR_ERRORS:
        return 0


def _normalize_color(color: object) -> tuple[int, int, int]:
    try:
        values: tuple[object, ...] = tuple(cast(Iterable[object], color))
    except _COLOR_ERRORS:
        values = ()
    if len(values) != 3:
        return (0, 0, 0)
    return (_clamp_channel(values[0]), _clamp_channel(values[1]), _clamp_channel(values[2]))


def _cell_key(key: object) -> tuple[int, int] | None:
    if isinstance(key, tuple) and len(key) == 2:
        try:
            return int(key[0]), int(key[1])
        except _COLOR_ERRORS:
            return None
    return None


class EmulatedKeyboardDevice:
    """Framebuffer device honoring one backend's capabilities and dimensions."""

    def __init__(
        self,
        *,
        backend_name: str,
        capabilities: BackendCapabilities,
        dimensions: tuple[int, int],
    ) -> None:
        self.backend_name = backend_name
        self.emulated = True
        self._capabilities = capabilities
        self._rows, self._cols = int(dimensions[0]), int(dimensions[1])
        self.supports_per_key = bool(capabilities.per_key)
        self._framebuffer: dict[tuple[int, int], tuple[int, int, int]] = {
            (row, col): (0, 0, 0) for row in range(self._rows) for col in range(self._cols)
        }
        self._brightness = 0
        self._off = True
        self._closed = False

    def _ensure_open(self) -> None:
        if self._closed:
            raise RuntimeError(f"Emulated device is closed: {self.backend_name}")

    def _log(self, action: str, **fields: object) -> None:
        if _debug_enabled():
            logger.debug(
                "Emulated device state changed: backend=%s action=%s fields=%s",
                self.backend_name,
                action,
                fields,
            )

    def _set_brightness(self, brightness: object) -> int:
        normalized = normalize_precise_brightness_value(brightness)
        self._brightness = normalized
        return normalized

    def _refresh_off(self) -> None:
        self._off = self._brightness <= 0 or all(color == (0, 0, 0) for color in self._framebuffer.values())

    def set_color(self, color: object, *, brightness: int) -> None:
        self._ensure_open()
        rgb = _normalize_color(color)
        for key in self._framebuffer:
            self._framebuffer[key] = rgb
        self._set_brightness(brightness)
        self._refresh_off()
        self._log("set_color", color=rgb, brightness=self._brightness, off=self._off)

    def set_key_colors(
        self,
        color_map: object,
        *,
        brightness: int,
        enable_user_mode: bool = True,
    ) -> None:
        self._ensure_open()
        del enable_user_mode
        mapping: Mapping[object, object]
        try:
            mapping = dict(cast(Mapping[object, object], color_map))
        except _MAP_ERRORS:
            mapping = {}
        written = 0
        for raw_key, raw_color in mapping.items():
            cell = _cell_key(raw_key)
            if cell is None or cell not in self._framebuffer:
                continue
            self._framebuffer[cell] = _normalize_color(raw_color)
            written += 1
        self._set_brightness(brightness)
        self._refresh_off()
        self._log("set_key_colors", written=written, brightness=self._brightness, off=self._off)

    def set_brightness(self, brightness: int) -> None:
        self._ensure_open()
        self._set_brightness(brightness)
        self._refresh_off()
        self._log("set_brightness", brightness=self._brightness, off=self._off)

    def get_brightness(self) -> int:
        self._ensure_open()
        return int(self._brightness)

    def turn_off(self) -> None:
        self._ensure_open()
        self._brightness = 0
        self._off = True
        self._log("turn_off")

    def is_off(self) -> bool:
        self._ensure_open()
        return bool(self._off)

    def get_color(self) -> tuple[int, int, int]:
        self._ensure_open()
        if not self._framebuffer:
            return (0, 0, 0)
        return next(iter(self._framebuffer.values()))

    def framebuffer(self) -> dict[tuple[int, int], tuple[int, int, int]]:
        self._ensure_open()
        return dict(self._framebuffer)

    def set_effect(self, *_args: object, **_kwargs: object) -> None:
        self._ensure_open()
        raise NotImplementedError("Emulated devices do not support hardware effects")

    def set_palette_color(self, *_args: object, **_kwargs: object) -> None:
        self._ensure_open()
        raise NotImplementedError("Emulated devices do not support palette writes")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._log("close")

    @property
    def closed(self) -> bool:
        return bool(self._closed)


_EMULATED_PRIMARY_STATES: dict[str, EmulatedKeyboardDevice] = {}


def emulated_device_for_backend(
    *,
    backend_name: str,
    capabilities: BackendCapabilities,
    dimensions: tuple[int, int],
) -> EmulatedKeyboardDevice:
    existing = _EMULATED_PRIMARY_STATES.get(backend_name)
    if existing is not None and not existing.closed:
        return existing
    device = EmulatedKeyboardDevice(
        backend_name=backend_name,
        capabilities=capabilities,
        dimensions=dimensions,
    )
    _EMULATED_PRIMARY_STATES[backend_name] = device
    return device


def reset_emulated_devices() -> None:
    """Clear in-memory primary emulation state (tests)."""

    _EMULATED_PRIMARY_STATES.clear()
