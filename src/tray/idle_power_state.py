"""Idle/power tray state owner and public facade.

The typed owner (``TrayIdlePowerState``) and ``ensure_tray_idle_power_state``
live here. Field-bridge and convenience-predicate implementations live in
sibling modules and are re-exported so existing import paths stay stable:

- ``src.tray._idle_power_fields`` — legacy attr ↔ owner sync/read/write
- ``src.tray._idle_power_predicates`` — forced-off / dim-temp / brightness helpers
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class TrayIdlePowerState:
    """Typed owner for idle/power runtime state.

    Legacy tray attributes remain the public seam; this owner enables explicit
    ownership while bridge helpers keep both representations synchronized.
    """

    idle_forced_off: bool = False
    user_forced_off: bool = False
    power_forced_off: bool = False
    dim_temp_active: bool = False
    dim_temp_target_brightness: Optional[int] = None
    dim_sync_suppressed_logged: bool = False
    last_idle_turn_off_at: float = 0.0
    last_resume_at: float = 0.0
    last_brightness: int = 25
    idle_restore_loop_effect_ramp: bool = False
    last_power_source_transition_at: float = 0.0
    last_power_source_transition_profile_name: Optional[str] = None
    hidden_perkey_restore_brightness_hint: Optional[int] = None
    hidden_perkey_restore_device_off_hint: Optional[bool] = None
    last_power_source_blank_recovery_at: float = 0.0
    last_hardware_blank_recovery_at: float = 0.0
    hardware_toggle_restore_effect: str = "none"
    hardware_toggle_restore_per_key_colors: dict[object, object] | None = None
    hardware_toggle_restore_software_target: str = "keyboard"
    hardware_toggle_restore_hardware_effect: str = "none"
    hardware_toggle_restore_hardware_color: object = None

    def reset_dim_state(self) -> None:
        self.dim_temp_active = False
        self.dim_temp_target_brightness = None


def ensure_tray_idle_power_state(tray: object) -> TrayIdlePowerState:
    """Ensure a tray has a typed `tray_idle_power_state` owner.

    Returns the existing owner when present and correctly typed. Otherwise,
    creates a fresh owner and best-effort attaches it to the tray.
    """

    existing = getattr(tray, "tray_idle_power_state", None)
    if isinstance(existing, TrayIdlePowerState):
        return existing

    st = TrayIdlePowerState()
    try:
        setattr(tray, "tray_idle_power_state", st)
    except AttributeError:
        pass
    return st


# Re-exports (WS1 / A2): field bridge + convenience predicates.
from src.tray._idle_power_fields import (  # noqa: E402,F401
    clear_idle_power_state_field,
    read_idle_power_state_bool_field,
    read_idle_power_state_float_field,
    read_idle_power_state_optional_bool_field,
    read_idle_power_state_optional_int_field,
    set_idle_power_state_field,
    sync_idle_power_state_field,
)
from src.tray._idle_power_predicates import (  # noqa: E402,F401
    any_forced_off,
    dim_temp_target_brightness,
    is_dim_temp_active,
    is_system_forced_off,
    is_user_forced_off,
    read_forced_off_flags,
    read_last_brightness,
    read_last_resume_at,
    reset_dim_state_on_tray,
    set_last_brightness,
)
