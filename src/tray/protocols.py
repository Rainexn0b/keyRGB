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
from typing import TYPE_CHECKING, Any, Callable, Optional, Protocol, runtime_checkable


if TYPE_CHECKING:
    from src.core.config import Config
    from src.core.effects.engine import EffectsEngine


# ---------------------------------------------------------------------------
# Idle/Power state - replaces _idle_forced_off, _user_forced_off, etc.
# ---------------------------------------------------------------------------

@dataclass
class IdlePowerState:
    """Typed state for idle/power management tracking.

    Replaces the pattern:
        if not hasattr(tray, "_idle_forced_off"):
            tray._idle_forced_off = False

    With:
        tray.idle_power_state.idle_forced_off = False
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

    visual: Optional[str] = None
    animating: bool = False


# ---------------------------------------------------------------------------
# Protocol for objects that have a config attribute
# ---------------------------------------------------------------------------

@runtime_checkable
class HasConfig(Protocol):
    """Protocol for objects with a Config-like attribute."""

    @property
    def config(self) -> "Config":
        ...


# ---------------------------------------------------------------------------
# Protocol for objects with an engine attribute
# ---------------------------------------------------------------------------

@runtime_checkable
class HasEngine(Protocol):
    """Protocol for objects with an EffectsEngine."""

    @property
    def engine(self) -> "EffectsEngine":
        ...


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
    config: Any  # Config
    engine: Any  # EffectsEngine

    # Lighting state
    is_off: bool

    # Last known brightness (for restore operations)
    @property
    def _last_brightness(self) -> int:
        ...

    @_last_brightness.setter
    def _last_brightness(self, value: int) -> None:
        ...

    # UI refresh hooks
    def _refresh_ui(self) -> None:
        ...

    def _update_menu(self) -> None:
        ...


# ---------------------------------------------------------------------------
# Minimal protocol for idle/power operations
# ---------------------------------------------------------------------------

@runtime_checkable
class IdlePowerTrayProtocol(Protocol):
    """Minimal protocol for idle/power polling functions.

    Narrower than TrayStateProtocol - only requires what idle_power_polling needs.
    """

    config: Any
    engine: Any
    is_off: bool

    # Idle power state (can be the IdlePowerState dataclass or duck-typed)
    _idle_forced_off: bool
    _user_forced_off: bool
    _power_forced_off: bool
    _dim_backlight_baselines: dict[str, int]
    _dim_temp_active: bool
    _dim_temp_target_brightness: Optional[int]


# ---------------------------------------------------------------------------
# Helper to initialize idle power state on a tray object
# ---------------------------------------------------------------------------

def ensure_idle_power_state(tray: Any) -> None:
    """Initialize idle power state attributes if missing.

    This is the migration helper - existing code can call this,
    new code should use IdlePowerState directly.
    """
    if not hasattr(tray, "_idle_forced_off"):
        tray._idle_forced_off = False
    if not hasattr(tray, "_user_forced_off"):
        tray._user_forced_off = False
    if not hasattr(tray, "_power_forced_off"):
        tray._power_forced_off = False
    if not hasattr(tray, "_dim_backlight_baselines"):
        tray._dim_backlight_baselines = {}
    if not hasattr(tray, "_dim_temp_active"):
        tray._dim_temp_active = False
    if not hasattr(tray, "_dim_temp_target_brightness"):
        tray._dim_temp_target_brightness = None


def ensure_tray_icon_state(tray: Any) -> None:
    """Initialize tray icon state attributes if missing."""
    if not hasattr(tray, "_tray_icon_visual"):
        tray._tray_icon_visual = None
    if not hasattr(tray, "_tray_icon_animating"):
        tray._tray_icon_animating = False
