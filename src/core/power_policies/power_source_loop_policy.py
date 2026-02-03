from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from .battery_saver_policy import BatterySaverPolicy
from .power_source_policy import compute_power_source_policy


@dataclass(frozen=True)
class TurnOffKeyboard:
    pass


@dataclass(frozen=True)
class RestoreKeyboard:
    pass


@dataclass(frozen=True)
class ApplyBrightness:
    brightness: int


PowerAction = Union[TurnOffKeyboard, RestoreKeyboard, ApplyBrightness]


@dataclass(frozen=True)
class PowerSourceLoopInputs:
    on_ac: bool
    now: float

    # Global enable
    power_management_enabled: bool

    # Current state (best-effort)
    current_brightness: int
    is_off: bool

    # Per power-source configuration
    ac_enabled: bool
    battery_enabled: bool
    ac_brightness_override: int | float | str | None
    battery_brightness_override: int | float | str | None

    # Legacy battery saver policy configuration
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

        self._battery_saver_policy = battery_saver_policy or BatterySaverPolicy()

    def update(self, inputs: PowerSourceLoopInputs) -> PowerSourceLoopResult:
        on_ac = bool(inputs.on_ac)
        now = float(inputs.now)

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

        actions: list[PowerAction] = []

        # Apply on/off on transitions (or when the desired enabled flag changes).
        if self._last_desired_enabled is None or bool(desired_enabled) != bool(self._last_desired_enabled):
            actions.append(RestoreKeyboard() if bool(desired_enabled) else TurnOffKeyboard())
            self._last_desired_enabled = bool(desired_enabled)

        # If disabled in this power state, do not apply brightness policies.
        if not bool(desired_enabled):
            return PowerSourceLoopResult(skip=False, actions=tuple(actions))

        if desired_brightness is not None:
            # Apply only when it actually changes.
            if self._last_desired_brightness is None or int(desired_brightness) != int(self._last_desired_brightness):
                if not bool(inputs.is_off):
                    actions.append(ApplyBrightness(int(desired_brightness)))
                self._last_desired_brightness = int(desired_brightness)
            return PowerSourceLoopResult(skip=False, actions=tuple(actions))

        # Legacy battery saver policy (dim on AC unplug, restore on replug)
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
        # legacy battery saver path.
        self._last_on_ac = on_ac

        return PowerSourceLoopResult(skip=False, actions=tuple(actions))
