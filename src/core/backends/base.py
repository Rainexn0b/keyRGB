from __future__ import annotations

from collections.abc import Callable, Mapping
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

    def close(self) -> None:
        """Release hardware resources held by this device.

        Safe to call multiple times. The default implementation is a no-op.
        """
        ...


@dataclass(frozen=True)
class BackendCapabilities:
    brightness: bool
    per_key: bool
    color: bool
    hardware_effects: bool
    palette: bool


DEFAULT_BACKEND_CAPABILITIES = BackendCapabilities(
    brightness=False,
    per_key=False,
    color=False,
    hardware_effects=False,
    palette=False,
)


def normalize_backend_capabilities(
    value: object | None,
    *,
    default: BackendCapabilities = DEFAULT_BACKEND_CAPABILITIES,
) -> BackendCapabilities:
    """Return one typed capability snapshot, failing closed for missing evidence."""

    if isinstance(value, BackendCapabilities):
        return value
    if value is None:
        return default

    def _field(name: str, fallback: bool) -> bool:
        raw = value.get(name, fallback) if isinstance(value, Mapping) else getattr(value, name, fallback)
        return bool(raw)

    return BackendCapabilities(
        brightness=_field("brightness", default.brightness),
        per_key=_field("per_key", default.per_key),
        color=_field("color", default.color),
        hardware_effects=_field("hardware_effects", default.hardware_effects),
        palette=_field("palette", default.palette),
    )


def supports_per_key_output(capabilities: object | None, device: object | None) -> bool:
    """Require both declared capability evidence and an operational writer."""

    declared = capabilities if capabilities is not None else getattr(device, "backend_caps", None)
    caps = normalize_backend_capabilities(declared)
    return caps.per_key and callable(getattr(device, "set_key_colors", None))


class BackendStability(str, Enum):
    VALIDATED = "validated"
    EXPERIMENTAL = "experimental"
    DORMANT = "dormant"


class ExperimentalEvidence(str, Enum):
    SPECULATIVE = "speculative"
    REVERSE_ENGINEERED = "reverse_engineered"


class BackendRole(str, Enum):
    """Classifies whether a backend participates in primary auto-selection.

    PRIMARY backends are candidates for normal selection; AUXILIARY backends
    are excluded from primary selection but remain visible in diagnostics and
    secondary-device workflows.
    """

    PRIMARY = "primary"
    AUXILIARY = "auxiliary"


@dataclass(frozen=True)
class BackendMetadata:
    """Static, serialisable metadata that describes a backend type.

    This is the single source of truth for provider, tier, safety, and
    stability classification.  It lives on the *package* (via
    ``BackendRegistration``) rather than on individual backend instances, so it
    is available **before** a backend is constructed and survives even if the
    factory fails.
    """

    name: str
    priority: int
    role: BackendRole = BackendRole.PRIMARY
    provider: str | None = None  # "kernel-sysfs", "usb-userspace"
    stability: BackendStability = BackendStability.VALIDATED
    experimental_evidence: ExperimentalEvidence | None = None

    def diagnostics_tier(self) -> int | None:
        """Diagnostics classification tier derived from *provider*.

        * 1 = kernel / sysfs backed
        * 2 = USB / userspace backed
        * None = unknown
        """
        p = (self.provider or "").strip().lower()
        if p == "kernel-sysfs":
            return 1
        if p == "usb-userspace":
            return 2
        return None

    def auto_safety_tier(self) -> int:
        """Auto-selection safety tier (1 = kernel preferred, 0 = userspace)."""
        return 1 if self.diagnostics_tier() == 1 else 0


@dataclass(frozen=True)
class BackendRegistration:
    """Package-owned built-in registration marker.

    Each backend package exposes a ``BACKEND_REGISTRATION`` module-level
    instance of this type.  The registry discovers these at scan time and
    derives ``BackendSpec`` objects from them without hand-edited import lists.
    """

    metadata: BackendMetadata
    factory: Callable[[], KeyboardBackend]


def _normalize_enum_text(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    return value.strip().lower()


def normalize_backend_stability(value: object) -> BackendStability:
    if isinstance(value, BackendStability):
        return value

    text = _normalize_enum_text(value)
    if text is None:
        return BackendStability.VALIDATED

    for item in BackendStability:
        if item.value == text:
            return item

    return BackendStability.VALIDATED


def normalize_experimental_evidence(value: object) -> ExperimentalEvidence | None:
    if isinstance(value, ExperimentalEvidence):
        return value

    text = _normalize_enum_text(value)
    if text is None:
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

    def effects(self) -> dict[str, Any]: ...

    def colors(self) -> dict[str, Any]: ...
