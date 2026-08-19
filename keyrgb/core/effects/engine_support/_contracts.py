"""Explicit state contract shared by effects-engine support mixins."""

from __future__ import annotations

from collections.abc import Callable
from threading import RLock, Thread
from typing import Protocol

from keyrgb.core.backends.base import BackendCapabilities

from ..device import Color, KeyboardDeviceProtocol, PerKeyColorMap


class EngineSupportContract(Protocol):
    """State and operations consumed across engine support mixins."""

    kb_lock: RLock
    kb: KeyboardDeviceProtocol
    backend_caps: BackendCapabilities
    device_available: bool
    running: bool
    thread: Thread | None
    speed: int
    brightness: int
    current_color: Color
    current_effect: str | None
    per_key_colors: PerKeyColorMap | None
    reactive_color: Color | None
    reactive_use_manual_color: bool
    direction: str | None
    _last_hw_mode_brightness: int | None
    _device_mode_off: bool
    _last_rendered_brightness: int | None
    _thread_generation: int
    _brightness_fade_token: int
    _brightness_fade_lock: RLock
    _permission_error_cb: Callable[[Exception], None] | None

    def stop(self) -> None: ...

    def _ensure_device_available(self) -> bool: ...

    def get_backend_effects(self) -> dict[str, Callable[..., object]]: ...

    def get_backend_colors(self) -> dict[str, object]: ...


_REQUIRED_ENGINE_SUPPORT_MEMBERS = (
    "kb_lock",
    "kb",
    "backend_caps",
    "device_available",
    "running",
    "thread",
    "speed",
    "brightness",
    "current_color",
    "current_effect",
    "per_key_colors",
    "reactive_color",
    "reactive_use_manual_color",
    "direction",
    "_last_hw_mode_brightness",
    "_device_mode_off",
    "_last_rendered_brightness",
    "_thread_generation",
    "_brightness_fade_token",
    "_brightness_fade_lock",
    "_permission_error_cb",
    "stop",
    "_ensure_device_available",
    "get_backend_effects",
    "get_backend_colors",
)


def assert_engine_support_contract(engine: object) -> None:
    """Fail during construction when mixin dependencies are incomplete."""

    missing = [name for name in _REQUIRED_ENGINE_SUPPORT_MEMBERS if not hasattr(engine, name)]
    if missing:
        raise TypeError(f"effects engine support contract is incomplete: {', '.join(missing)}")
