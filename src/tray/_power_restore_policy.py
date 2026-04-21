"""Power-restore guard and policy normalization for tray lighting.

Extracted from protocols.py to keep that module below the refactor threshold.
Public names are re-exported from src.tray.protocols for backward compatibility.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Optional, Protocol

from src.tray.idle_power_state import (
    read_idle_power_state_bool_field,
    set_idle_power_state_field,
)


@dataclass(frozen=True)
class LightingPowerRestoreGuardState:
    """Normalized forced-off flags used by power-restore guard policy.

    `None` means the field was intentionally not read due to short-circuiting.
    """

    user_forced_off: bool
    idle_forced_off: Optional[bool]
    power_forced_off: Optional[bool]


@dataclass(frozen=True)
class LightingPowerRestorePolicyState:
    """Normalized restore policy consumed by power-restore execution."""

    guard_state: LightingPowerRestoreGuardState
    should_log_power_restore: bool
    should_restore: bool
    is_loop_effect: bool


class _HasPowerRestoreNormalizationInputs(Protocol):
    @property
    def config(self) -> object: ...

    @property
    def _last_brightness(self) -> int: ...


def read_lighting_power_restore_guard_state(tray: object) -> LightingPowerRestoreGuardState:
    """Read forced-off guard flags in restore-policy order.

    Preserve legacy short-circuit behavior by not touching lower-priority flags
    once a higher-priority forced-off condition is active.
    """

    user_forced_off = read_idle_power_state_bool_field(
        tray,
        attr_name="_user_forced_off",
        state_name="user_forced_off",
        default=False,
    )
    if user_forced_off:
        return LightingPowerRestoreGuardState(
            user_forced_off=True,
            idle_forced_off=None,
            power_forced_off=None,
        )

    idle_forced_off = read_idle_power_state_bool_field(
        tray,
        attr_name="_idle_forced_off",
        state_name="idle_forced_off",
        default=False,
    )
    if idle_forced_off:
        return LightingPowerRestoreGuardState(
            user_forced_off=False,
            idle_forced_off=True,
            power_forced_off=None,
        )

    power_forced_off = read_idle_power_state_bool_field(
        tray,
        attr_name="_power_forced_off",
        state_name="power_forced_off",
        default=False,
    )
    return LightingPowerRestoreGuardState(
        user_forced_off=False,
        idle_forced_off=False,
        power_forced_off=power_forced_off,
    )


def normalize_lighting_power_restore_policy_state(
    tray: _HasPowerRestoreNormalizationInputs,
    *,
    safe_int_attr_fn: Callable[..., int],
    safe_str_attr_fn: Callable[..., str],
    is_software_effect_fn: Callable[[str], bool],
    is_reactive_effect_fn: Callable[[str], bool],
) -> LightingPowerRestorePolicyState:
    """Normalize guard/policy state for lighting power restore.

    This function owns policy normalization and compatibility convergence.
    Callers perform execution side effects based on the returned plan.
    """

    guard_state = read_lighting_power_restore_guard_state(tray)
    if guard_state.user_forced_off:
        return LightingPowerRestorePolicyState(
            guard_state=guard_state,
            should_log_power_restore=False,
            should_restore=False,
            is_loop_effect=False,
        )

    if guard_state.idle_forced_off is True:
        return LightingPowerRestorePolicyState(
            guard_state=guard_state,
            should_log_power_restore=False,
            should_restore=False,
            is_loop_effect=False,
        )

    should_log_power_restore = guard_state.power_forced_off is True
    if should_log_power_restore:
        set_idle_power_state_field(
            tray,
            attr_name="_power_forced_off",
            state_name="power_forced_off",
            value=False,
        )
        set_idle_power_state_field(
            tray,
            attr_name="_idle_forced_off",
            state_name="idle_forced_off",
            value=False,
        )

        if safe_int_attr_fn(tray.config, "brightness", default=0) == 0:
            setattr(tray.config, "brightness", tray._last_brightness if tray._last_brightness > 0 else 25)

    if safe_int_attr_fn(tray.config, "brightness", default=0) == 0:
        return LightingPowerRestorePolicyState(
            guard_state=guard_state,
            should_log_power_restore=should_log_power_restore,
            should_restore=False,
            is_loop_effect=False,
        )

    effect_name = safe_str_attr_fn(tray.config, "effect", default="none") or "none"
    is_loop_effect = bool(is_software_effect_fn(effect_name) or is_reactive_effect_fn(effect_name))
    return LightingPowerRestorePolicyState(
        guard_state=guard_state,
        should_log_power_restore=should_log_power_restore,
        should_restore=True,
        is_loop_effect=is_loop_effect,
    )
