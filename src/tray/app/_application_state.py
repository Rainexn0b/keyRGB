"""Typed bootstrap state for the tray application facade."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from src.tray.protocols import TrayIconState


if TYPE_CHECKING:
    from src.core.config import Config
    from src.tray.idle_power_state import TrayIdlePowerState


class _TrayPreBootstrapWritable(Protocol):
    icon: object | None
    is_off: bool
    tray_icon_state: TrayIconState
    tray_idle_power_state: TrayIdlePowerState
    _power_forced_off: bool
    _user_forced_off: bool
    _idle_forced_off: bool
    _dim_temp_active: bool
    _dim_temp_target_brightness: int | None
    _dim_backlight_baselines: dict[str, int]
    _dim_backlight_dimmed: dict[str, bool]
    _dim_screen_off: bool
    _dim_sync_suppressed_logged: bool
    _last_brightness: int
    _last_resume_at: float
    _event_last_at: dict[str, float]
    _permission_notice_sent: bool
    _pending_notifications: list[tuple[str, str]]


@dataclass(slots=True)
class TrayPreBootstrapState:
    icon: object | None
    is_off: bool
    tray_icon_state: TrayIconState
    tray_idle_power_state: TrayIdlePowerState
    power_forced_off: bool
    user_forced_off: bool
    idle_forced_off: bool
    dim_temp_active: bool
    dim_temp_target_brightness: int | None
    dim_backlight_baselines: dict[str, int]
    dim_backlight_dimmed: dict[str, bool]
    dim_screen_off: bool
    dim_sync_suppressed_logged: bool
    last_brightness: int
    last_resume_at: float
    event_last_at: dict[str, float]
    permission_notice_sent: bool
    pending_notifications: list[tuple[str, str]]

    def apply_to(self, tray: _TrayPreBootstrapWritable) -> None:
        tray.icon = self.icon
        tray.is_off = self.is_off
        tray.tray_icon_state = self.tray_icon_state
        tray.tray_idle_power_state = self.tray_idle_power_state
        tray._power_forced_off = self.power_forced_off
        tray._user_forced_off = self.user_forced_off
        tray._idle_forced_off = self.idle_forced_off
        tray._dim_temp_active = self.dim_temp_active
        tray._dim_temp_target_brightness = self.dim_temp_target_brightness
        tray._dim_backlight_baselines = self.dim_backlight_baselines
        tray._dim_backlight_dimmed = self.dim_backlight_dimmed
        tray._dim_screen_off = self.dim_screen_off
        tray._dim_sync_suppressed_logged = self.dim_sync_suppressed_logged
        tray._last_brightness = self.last_brightness
        tray._last_resume_at = self.last_resume_at
        tray._event_last_at = self.event_last_at
        tray._permission_notice_sent = self.permission_notice_sent
        tray._pending_notifications = self.pending_notifications


class _TrayBootstrapWritable(Protocol):
    config: Config
    engine: object
    backend: object | None
    backend_probe: object | None
    backend_caps: object | None
    device_discovery: object | None
    selected_device_context: str
    _ite_rows: int
    _ite_cols: int


@dataclass(slots=True)
class TrayBootstrapState:
    config: Config
    engine: object
    power_manager_factory: object
    backend: object | None
    backend_probe: object | None
    backend_caps: object | None
    device_discovery: object | None
    selected_device_context: str
    ite_rows: int
    ite_cols: int

    def apply_to(self, tray: _TrayBootstrapWritable) -> None:
        tray.config = self.config
        tray.engine = self.engine
        tray.backend = self.backend
        tray.backend_probe = self.backend_probe
        tray.backend_caps = self.backend_caps
        tray.device_discovery = self.device_discovery
        tray.selected_device_context = self.selected_device_context
        tray._ite_rows = self.ite_rows
        tray._ite_cols = self.ite_cols
