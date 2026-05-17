from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from .battery_saver_policy import BatterySaverPolicy
from .power_source_policy import compute_power_source_policy
from ..system import PowerMode


@dataclass(frozen=True)
class TurnOffKeyboard:
    pass


@dataclass(frozen=True)
class RestoreKeyboard:
    pass


@dataclass(frozen=True)
class ApplyBrightness:
    brightness: int


@dataclass(frozen=True)
class ActivatePowerMode:
    mode: PowerMode


@dataclass(frozen=True)
class ActivatePerkeyProfile:
    profile_name: str


PowerAction = Union[
    TurnOffKeyboard,
    RestoreKeyboard,
    ApplyBrightness,
    ActivatePowerMode,
    ActivatePerkeyProfile,
]


@dataclass(frozen=True)
class PowerSourceLoopInputs:
    on_ac: bool
    now: float

    # Global enable
    power_management_enabled: bool

    # Current state (best-effort)
    current_brightness: int
    is_off: bool
    active_power_mode: PowerMode | None
    active_perkey_profile_name: str | None

    # Per power-source configuration
    ac_enabled: bool
    battery_enabled: bool
    ac_brightness_override: int | float | str | None
    battery_brightness_override: int | float | str | None
    ac_power_mode: PowerMode | None
    battery_power_mode: PowerMode | None
    ac_perkey_profile_name: str | None
    battery_perkey_profile_name: str | None

    # Battery saver policy configuration
    battery_saver_enabled: bool
    battery_saver_brightness: int


@dataclass(frozen=True)
class PowerSourceLoopResult:
    skip: bool
    actions: tuple[PowerAction, ...]


class PowerSourceLoopPolicy:
    """State machine behind PowerManager's AC/battery polling loop.

    This is designed to be unit-testable: it performs no IO and does not call the
    keyboard controller directly; it only returns suggested actions.
    """

    def __init__(
        self,
        *,
        debounce_seconds: float = 3.0,
        battery_saver_policy: BatterySaverPolicy | None = None,
    ) -> None:
        self._debounce_seconds = float(debounce_seconds)
        self._last_on_ac: Optional[bool] = None
        self._last_change_ts: float = 0.0

        self._last_desired_enabled: Optional[bool] = None
        self._last_desired_brightness: Optional[int] = None
        self._last_desired_power_mode: Optional[str] = None
        self._last_desired_perkey_profile: Optional[str] = None

        self._battery_saver_policy = battery_saver_policy or BatterySaverPolicy()

    def update(self, inputs: PowerSourceLoopInputs) -> PowerSourceLoopResult:
        on_ac = bool(inputs.on_ac)
        now = float(inputs.now)
        try:
            current_brightness = int(inputs.current_brightness)
        except (TypeError, ValueError):
            current_brightness = 0
        current_enabled = bool(current_brightness > 0 and not bool(inputs.is_off))

        # Debounce rapid toggling.
        if self._last_on_ac is not None and on_ac != bool(self._last_on_ac):
            if now - float(self._last_change_ts) < float(self._debounce_seconds):
                return PowerSourceLoopResult(skip=True, actions=())
            self._last_on_ac = on_ac
            self._last_change_ts = now
        elif self._last_on_ac is None:
            self._last_on_ac = on_ac
            self._last_change_ts = now

        if not bool(inputs.power_management_enabled):
            return PowerSourceLoopResult(skip=False, actions=())

        desired_enabled, desired_brightness = compute_power_source_policy(
            on_ac=on_ac,
            ac_enabled=bool(inputs.ac_enabled),
            battery_enabled=bool(inputs.battery_enabled),
            ac_brightness_override=inputs.ac_brightness_override,
            battery_brightness_override=inputs.battery_brightness_override,
        )
        desired_power_mode = inputs.ac_power_mode if bool(on_ac) else inputs.battery_power_mode
        desired_perkey_profile_name = (
            inputs.ac_perkey_profile_name if bool(on_ac) else inputs.battery_perkey_profile_name
        )
        current_power_mode = inputs.active_power_mode
        current_perkey_profile_name = str(inputs.active_perkey_profile_name or "").strip() or None

        actions: list[PowerAction] = []

        # Apply on/off only when the desired state actually differs from the
        # current state on the first tick, or when the desired state changes
        # on later ticks. This avoids redundant startup restores that can
        # restart a running reactive effect and cause a visible flash.
        should_apply_enabled = False
        if self._last_desired_enabled is None:
            should_apply_enabled = bool(desired_enabled) != bool(current_enabled)
        else:
            should_apply_enabled = bool(desired_enabled) != bool(self._last_desired_enabled)

        if should_apply_enabled:
            actions.append(RestoreKeyboard() if bool(desired_enabled) else TurnOffKeyboard())

        self._last_desired_enabled = bool(desired_enabled)

        # If disabled in this power state, do not apply brightness policies.
        if not bool(desired_enabled):
            self._last_desired_power_mode = desired_power_mode.value if desired_power_mode is not None else None
            self._last_desired_perkey_profile = desired_perkey_profile_name
            return PowerSourceLoopResult(skip=False, actions=tuple(actions))

        should_apply_power_mode = False
        if desired_power_mode is not None:
            if self._last_desired_power_mode is None:
                should_apply_power_mode = desired_power_mode != current_power_mode
            else:
                should_apply_power_mode = desired_power_mode.value != self._last_desired_power_mode
        if should_apply_power_mode and desired_power_mode is not None:
            actions.append(ActivatePowerMode(desired_power_mode))
        self._last_desired_power_mode = desired_power_mode.value if desired_power_mode is not None else None

        should_apply_perkey_profile = False
        if desired_perkey_profile_name is not None:
            if self._last_desired_perkey_profile is None:
                should_apply_perkey_profile = desired_perkey_profile_name != current_perkey_profile_name
            else:
                should_apply_perkey_profile = desired_perkey_profile_name != self._last_desired_perkey_profile
        if should_apply_perkey_profile and desired_perkey_profile_name is not None:
            actions.append(ActivatePerkeyProfile(desired_perkey_profile_name))
        self._last_desired_perkey_profile = desired_perkey_profile_name

        if desired_brightness is not None:
            # Apply only when it actually changes.
            should_apply_brightness = False
            if self._last_desired_brightness is None:
                should_apply_brightness = int(desired_brightness) != int(current_brightness)
            else:
                should_apply_brightness = int(desired_brightness) != int(self._last_desired_brightness)

            if should_apply_brightness:
                if not bool(inputs.is_off):
                    actions.append(ApplyBrightness(int(desired_brightness)))
                self._last_desired_brightness = int(desired_brightness)
            elif self._last_desired_brightness is None:
                self._last_desired_brightness = int(desired_brightness)
            return PowerSourceLoopResult(skip=False, actions=tuple(actions))

        # Battery saver policy (dim on AC unplug, restore on replug)
        # when no explicit battery brightness override is configured.
        self._battery_saver_policy.configure(
            enabled=bool(inputs.battery_saver_enabled),
            target_brightness=int(inputs.battery_saver_brightness),
        )

        action_brightness = self._battery_saver_policy.update(
            on_ac=on_ac,
            current_brightness=int(inputs.current_brightness),
            is_off=bool(inputs.is_off),
            now=now,
        )

        if action_brightness is not None and self._last_on_ac is not None:
            actions.append(ApplyBrightness(int(action_brightness)))

        # Match previous loop behavior: last_on_ac is refreshed here only for the
        # battery saver path.
        self._last_on_ac = on_ac

        return PowerSourceLoopResult(skip=False, actions=tuple(actions))
