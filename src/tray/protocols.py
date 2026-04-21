"""Typed state protocols for the tray application.

This module defines Protocol classes for duck-typed objects passed throughout
the tray codebase. Using Protocols instead of untyped parameters enables:
1. Static type checking
2. IDE autocompletion
3. Explicit documentation of required interfaces
4. Clearer shared tray state
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Protocol, runtime_checkable

from src.tray.idle_power_state import (
    TrayIdlePowerState,
    ensure_tray_idle_power_state,
    read_idle_power_state_bool_field,
    read_idle_power_state_optional_int_field,
    set_idle_power_state_field,
    sync_idle_power_state_field,
)
from src.tray._power_restore_policy import (
    LightingPowerRestoreGuardState,
    LightingPowerRestorePolicyState,
    read_lighting_power_restore_guard_state,
    normalize_lighting_power_restore_policy_state,
)


if TYPE_CHECKING:
    from src.core.config import Config
    from src.core.effects.engine import EffectsEngine
    from src.tray.ui.icon import IconVisual


# ---------------------------------------------------------------------------
# Tray icon state
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

    config: "Config"


# ---------------------------------------------------------------------------
# Protocol for objects with an engine attribute
# ---------------------------------------------------------------------------


@runtime_checkable
class HasEngine(Protocol):
    """Protocol for objects with an EffectsEngine."""

    engine: "EffectsEngine"


# ---------------------------------------------------------------------------
# Shared tray runtime state building blocks
# ---------------------------------------------------------------------------


class _HasBackend(Protocol):
    backend: object | None


class _HasLightingPowerState(Protocol):
    is_off: bool
    _idle_forced_off: bool
    _user_forced_off: bool
    _power_forced_off: bool


class _HasLastBrightness(Protocol):
    @property
    def _last_brightness(self) -> int: ...

    @_last_brightness.setter
    def _last_brightness(self, value: int) -> None: ...


class _HasLastResumeAt(Protocol):
    _last_resume_at: float


class _HasSelectedDeviceContext(Protocol):
    selected_device_context: str


class _HasIdleDimState(Protocol):
    _dim_backlight_baselines: dict[str, int]
    _dim_backlight_dimmed: dict[str, bool]
    _dim_temp_active: bool
    _dim_temp_target_brightness: Optional[int]
    _dim_screen_off: bool
    _dim_sync_suppressed_logged: bool


class _RefreshUi(Protocol):
    def _refresh_ui(self) -> None: ...


class _RefreshTrayUi(_RefreshUi, Protocol):
    def _update_menu(self) -> None: ...


class _StartsCurrentEffect(Protocol):
    def _start_current_effect(self, **kwargs: object) -> None: ...


class _TrayLogging(Protocol):
    def _log_exception(self, msg: str, exc: Exception) -> None: ...

    def _log_event(self, source: str, action: str, **fields: object) -> None: ...


class _PermissionIssueNotifier(Protocol):
    def _notify_permission_issue(self, exc: Exception) -> None: ...


# ---------------------------------------------------------------------------
# Full tray protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class TrayStateProtocol(
    HasConfig,
    HasEngine,
    _HasLightingPowerState,
    _HasLastBrightness,
    _RefreshTrayUi,
    Protocol,
):
    """Core runtime state shared across tray controllers and pollers.

    This allows static type checking while maintaining duck typing.
    Functions with untyped `tray` parameters can be migrated to `tray: TrayStateProtocol`.
    """


# ---------------------------------------------------------------------------
# Minimal protocol for idle/power operations
# ---------------------------------------------------------------------------


@runtime_checkable
class IdlePowerTrayProtocol(
    HasConfig,
    HasEngine,
    _HasBackend,
    _HasLightingPowerState,
    _HasIdleDimState,
    _HasLastResumeAt,
    _RefreshUi,
    _TrayLogging,
    Protocol,
):
    """Minimal protocol for idle/power polling functions.

    Narrower than TrayStateProtocol - only requires what idle_power_polling needs.
    """


# ---------------------------------------------------------------------------
def ensure_tray_icon_state(tray: object) -> TrayIconState:
    """Return the tray icon state. The state must already be owned by the tray at init."""

    st = getattr(tray, "tray_icon_state", None)
    if not isinstance(st, TrayIconState):
        # Fallback for objects outside the normal tray lifecycle (e.g. test stubs).
        return TrayIconState()
    return st


# ---------------------------------------------------------------------------
# Minimal protocol for config polling / apply-from-config
# ---------------------------------------------------------------------------


@runtime_checkable
class ConfigPollingTrayProtocol(
    HasConfig,
    HasEngine,
    _HasLightingPowerState,
    _HasLastBrightness,
    _RefreshTrayUi,
    _StartsCurrentEffect,
    _TrayLogging,
    Protocol,
):
    """Minimal protocol for config polling + apply-from-config helpers."""


# ---------------------------------------------------------------------------
# Minimal protocol for tray lighting controller
# ---------------------------------------------------------------------------


@runtime_checkable
class LightingTrayProtocol(
    HasConfig,
    HasEngine,
    _HasLightingPowerState,
    _HasLastBrightness,
    _HasLastResumeAt,
    _HasSelectedDeviceContext,
    _RefreshTrayUi,
    _TrayLogging,
    _PermissionIssueNotifier,
    Protocol,
):
    """Minimal protocol for tray lighting controller functions."""



