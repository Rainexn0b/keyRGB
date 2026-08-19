"""Idle/power tray state owner and public facade.

The typed owner (``TrayIdlePowerState``) and ``ensure_tray_idle_power_state``
live here. Field-bridge and convenience-predicate implementations live in
sibling modules and are re-exported so existing import paths stay stable:

- ``keyrgb.tray._idle_power_fields`` — legacy attr ↔ owner sync/read/write
- ``keyrgb.tray._idle_power_predicates`` — forced-off / dim-temp / brightness helpers
"""

from __future__ import annotations

from dataclasses import dataclass


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
    dim_temp_target_brightness: int | None = None
    dim_sync_suppressed_logged: bool = False
    last_idle_turn_off_at: float = 0.0
    last_resume_at: float = 0.0
    last_brightness: int = 25
    idle_restore_loop_effect_ramp: bool = False
    last_power_source_transition_at: float = 0.0
    last_power_source_transition_profile_name: str | None = None
    hidden_perkey_restore_brightness_hint: int | None = None
    hidden_perkey_restore_device_off_hint: bool | None = None
    last_power_source_blank_recovery_at: float = 0.0
    last_hardware_blank_recovery_at: float = 0.0
    # Consecutive stable-zero recovery attempts that did not restore a non-zero
    # brightness read.  Drives the circuit breaker in
    # ``should_attempt_stable_zero_brightness_recovery`` so ITE controllers
    # that persistently report a transient 0 do not restart-spam the keyboard.
    stable_zero_recovery_attempt_count: int = 0
    # Timestamp of a fresh polled zero-brightness transition (device not off)
    # that still needs its stable-zero confirmation poll.  While recent, the
    # hardware poller uses the fast interval so the confirmation — and the
    # recovery it gates — happens in ~0.25 s instead of a full 2 s cycle,
    # halving the visible dark time of an ITE controller sleep.
    pending_zero_confirm_at: float = 0.0
    # Controller-initiated sleep treated as a valid off state (opt-in via the
    # controller_sleep_respect setting): the ITE firmware's ~10-minute
    # keyboard-input timeout blanked the deck and KeyRGB leaves it dark until
    # new input, a power restore, or a manual turn-on arrives.
    controller_sleep_off: bool = False
    controller_sleep_off_at: float = 0.0
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
        setattr(tray, "tray_idle_power_state", st)  # noqa: B010 – object-typed arg; setattr bypasses mypy attr-defined
    except AttributeError:
        pass
    return st


# Re-exports (WS1 / A2): field bridge + convenience predicates.
from keyrgb.tray._idle_power_fields import (  # noqa: F401
    clear_idle_power_state_field,
    read_idle_power_state_bool_field,
    read_idle_power_state_float_field,
    read_idle_power_state_optional_bool_field,
    read_idle_power_state_optional_int_field,
    set_idle_power_state_field,
    sync_idle_power_state_field,
)
from keyrgb.tray._idle_power_predicates import (  # noqa: F401
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
