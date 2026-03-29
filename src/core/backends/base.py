from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
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
class HardwareEffectDescriptor:
    """Typed backend-owned description for a hardware lighting effect."""

    build: Callable[..., Any]
    supported_args: frozenset[str] = field(default_factory=frozenset)

    def __call__(self, **kwargs: Any) -> Any:
        return self.build(**kwargs)


def legacy_builder_supported_args(effect_builder: Callable[..., Any]) -> frozenset[str]:
    """Best-effort extraction of supported kwargs from legacy closure builders.

    This exists only to wrap third-party callable effect builders into typed
    `HardwareEffectDescriptor` instances at backend boundaries.
    """

    try:
        freevars = getattr(effect_builder, "__code__").co_freevars
        closure = getattr(effect_builder, "__closure__")
        if not freevars or not closure:
            return frozenset()
        mapping = dict(zip(freevars, [c.cell_contents for c in closure]))
        args = mapping.get("args")
        if isinstance(args, dict):
            return frozenset(str(key) for key in args.keys())
    except Exception:
        return frozenset()
    return frozenset()


def make_hardware_effect_descriptor(
    builder: Callable[..., Any], *, supported_args: tuple[str, ...] | list[str] | set[str] | frozenset[str] = ()
) -> HardwareEffectDescriptor:
    """Create a typed hardware effect descriptor for backend effect maps."""

    return HardwareEffectDescriptor(build=builder, supported_args=frozenset(str(arg) for arg in supported_args))


class BackendStability(str, Enum):
    VALIDATED = "validated"
    EXPERIMENTAL = "experimental"
    DORMANT = "dormant"


class ExperimentalEvidence(str, Enum):
    SPECULATIVE = "speculative"
    REVERSE_ENGINEERED = "reverse_engineered"


def normalize_backend_stability(value: object) -> BackendStability:
    try:
        if isinstance(value, BackendStability):
            return value
        text = str(value or "").strip().lower()
    except Exception:
        return BackendStability.VALIDATED

    for item in BackendStability:
        if item.value == text:
            return item

    return BackendStability.VALIDATED


def normalize_experimental_evidence(value: object) -> ExperimentalEvidence | None:
    try:
        if isinstance(value, ExperimentalEvidence):
            return value
        text = str(value or "").strip().lower()
    except Exception:
        return None

    for item in ExperimentalEvidence:
        if item.value == text:
            return item

    return None


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
    stability: BackendStability | str
    experimental_evidence: ExperimentalEvidence | str | None

    def is_available(self) -> bool: ...

    def capabilities(self) -> BackendCapabilities: ...

    def get_device(self) -> KeyboardDevice: ...

    def dimensions(self) -> tuple[int, int]: ...

    def effects(self) -> dict[str, HardwareEffectDescriptor]: ...

    def colors(self) -> dict[str, Any]: ...
