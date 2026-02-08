from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class KeyboardDevice(Protocol):
    """Minimal protocol for keyboard devices.

    Backends can implement more, but these are the primitives KeyRGB uses today.
    """

    def turn_off(self) -> None: ...

    def is_off(self) -> bool: ...

    def get_brightness(self) -> int: ...

    def set_brightness(self, brightness: int) -> None: ...

    def set_color(self, color, *, brightness: int): ...

    def set_key_colors(self, color_map, *, brightness: int, enable_user_mode: bool = True): ...

    def set_effect(self, effect_data) -> None: ...


@dataclass(frozen=True)
class BackendCapabilities:
    per_key: bool
    color: bool
    hardware_effects: bool
    palette: bool


@dataclass(frozen=True)
class ProbeResult:
    """Result of probing a backend for availability on this system.

    `available` should be True only when the backend is plausibly usable.
    `confidence` is a rough 0..100 score used for auto-selection.
    """

    available: bool
    reason: str = ""
    confidence: int = 0
    identifiers: dict[str, str] = field(default_factory=dict)


class KeyboardBackend(Protocol):
    """Backend interface.

    This is intentionally small: it allows selecting a backend and exposing a
    consistent-ish surface while we keep the current UX stable.
    """

    name: str
    priority: int

    def is_available(self) -> bool: ...

    def capabilities(self) -> BackendCapabilities: ...

    def get_device(self) -> KeyboardDevice: ...

    def dimensions(self) -> tuple[int, int]: ...

    def effects(self) -> dict[str, Any]: ...

    def colors(self) -> dict[str, Any]: ...
