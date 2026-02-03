"""Typed state protocols for the tray application.

This module defines Protocol classes for duck-typed objects passed throughout
the tray codebase. Using Protocols instead of `Any` enables:
1. Static type checking
2. IDE autocompletion
3. Explicit documentation of required interfaces
4. Gradual migration from dynamic attributes

Migration path:
- Replace `tray: Any` with `tray: TrayStateProtocol`
- Replace dynamic hasattr/setattr with explicit state initialization
- Use IdlePowerState dataclass for dim/power tracking
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable


if TYPE_CHECKING:
    from src.core.config import Config
    from src.core.effects.engine import EffectsEngine
    from src.tray.ui.icon import IconVisual


# ---------------------------------------------------------------------------
# Idle/Power state - replaces _idle_forced_off, _user_forced_off, etc.
# ---------------------------------------------------------------------------


@dataclass
class IdlePowerState:
    """Typed state for idle/power management tracking.

    Intended to replace scattered per-function initialization of private tray
    attributes with a single typed state container.
    """

    idle_forced_off: bool = False
    user_forced_off: bool = False
    power_forced_off: bool = False

    # Screen dim sync state
    dim_backlight_baselines: dict[str, int] = field(default_factory=dict)
    dim_backlight_dimmed: dict[str, bool] = field(default_factory=dict)
    dim_temp_active: bool = False
    dim_temp_target_brightness: Optional[int] = None
    dim_screen_off: bool = False

    # Resume tracking
    last_resume_at: float = 0.0


# ---------------------------------------------------------------------------
# Tray icon state - replaces _tray_icon_visual, _tray_icon_animating
# ---------------------------------------------------------------------------


@dataclass
class TrayIconState:
    """Typed state for tray icon appearance tracking."""

    visual: Optional["IconVisual"] = None
    animating: bool = False


# ---------------------------------------------------------------------------
# Protocol for objects that have a config attribute
# ---------------------------------------------------------------------------


@runtime_checkable
class HasConfig(Protocol):
    """Protocol for objects with a Config-like attribute."""

    @property
    def config(self) -> "Config": ...


# ---------------------------------------------------------------------------
# Protocol for objects with an engine attribute
# ---------------------------------------------------------------------------


@runtime_checkable
class HasEngine(Protocol):
    """Protocol for objects with an EffectsEngine."""

    @property
    def engine(self) -> "EffectsEngine": ...


# ---------------------------------------------------------------------------
# Full tray protocol (for gradual adoption)
# ---------------------------------------------------------------------------


@runtime_checkable
class TrayStateProtocol(Protocol):
    """Protocol defining the expected interface for tray objects.

    This allows static type checking while maintaining duck typing.
    Functions accepting `tray: Any` can be migrated to `tray: TrayStateProtocol`.
    """

    # Core components
    config: "Config"
    engine: "EffectsEngine"

    # Lighting state
    is_off: bool

    # Last known brightness (for restore operations)
    @property
    def _last_brightness(self) -> int: ...

    @_last_brightness.setter
    def _last_brightness(self, value: int) -> None: ...

    # UI refresh hooks
    def _refresh_ui(self) -> None: ...

    def _update_menu(self) -> None: ...


# ---------------------------------------------------------------------------
# Minimal protocol for idle/power operations
# ---------------------------------------------------------------------------


@runtime_checkable
class IdlePowerTrayProtocol(Protocol):
    """Minimal protocol for idle/power polling functions.

    Narrower than TrayStateProtocol - only requires what idle_power_polling needs.
    """

    config: "Config"
    engine: "EffectsEngine"
    is_off: bool

    # Idle power state (can be the IdlePowerState dataclass or duck-typed)
    _idle_forced_off: bool
    _user_forced_off: bool
    _power_forced_off: bool
    _dim_backlight_baselines: dict[str, int]
    _dim_backlight_dimmed: dict[str, bool]
    _dim_temp_active: bool
    _dim_temp_target_brightness: Optional[int]
    _dim_screen_off: bool

    # Resume tracking
    _last_resume_at: float

    # Logging helpers (best-effort, but present on the real tray implementation)
    def _log_exception(self, msg: str, exc: Exception) -> None: ...

    def _log_event(self, source: str, action: str, **fields: object) -> None: ...


# ---------------------------------------------------------------------------
def ensure_tray_icon_state(tray: object) -> TrayIconState:
    """Ensure a tray has a `tray_icon_state` attribute and return it.

    Uses a *public* attribute name to avoid private hasattr/setattr coupling.
    Also migrates legacy `_tray_icon_*` values into the state object when present.
    """

    existing = getattr(tray, "tray_icon_state", None)
    if isinstance(existing, TrayIconState):
        return existing

    try:
        legacy_visual = getattr(tray, "_tray_icon_visual", None)
    except Exception:
        legacy_visual = None
    try:
        legacy_animating = bool(getattr(tray, "_tray_icon_animating", False))
    except Exception:
        legacy_animating = False

    st = TrayIconState(visual=legacy_visual, animating=legacy_animating)
    try:
        setattr(tray, "tray_icon_state", st)
    except Exception:
        pass
    return st


# ---------------------------------------------------------------------------
# Minimal protocol for config polling / apply-from-config
# ---------------------------------------------------------------------------


@runtime_checkable
class ConfigPollingTrayProtocol(Protocol):
    """Minimal protocol for config polling + apply-from-config helpers."""

    config: "Config"
    engine: "EffectsEngine"

    is_off: bool

    _idle_forced_off: bool
    _user_forced_off: bool
    _power_forced_off: bool

    @property
    def _last_brightness(self) -> int: ...

    @_last_brightness.setter
    def _last_brightness(self, value: int) -> None: ...

    def _refresh_ui(self) -> None: ...

    def _update_menu(self) -> None: ...

    def _start_current_effect(self) -> None: ...

    def _log_exception(self, msg: str, exc: Exception) -> None: ...

    def _log_event(self, source: str, action: str, **fields: object) -> None: ...
