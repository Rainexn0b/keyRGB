"""Pure decision helpers for hardware brightness polling (no tray I/O)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


_BRIGHTNESS_COERCION_ERRORS = (TypeError, ValueError, OverflowError)

DEFAULT_HARDWARE_POLL_INTERVAL_S = 2.0
FAST_HARDWARE_POLL_INTERVAL_S = 0.25
POWER_SOURCE_RECOVERY_WINDOW_S = 6.0
POWER_SOURCE_RECOVERY_COOLDOWN_S = 0.75
STABLE_ZERO_BRIGHTNESS_RECOVERY_COOLDOWN_S = 5.0


BrightnessPersistKind = Literal[
    "ignore_dim_temp_transient",
    "track_dim_temp_match",
    "ignore_power_forced_zero",
    "recover_power_source_blank",
    "ignore_zero_without_off",
    "mark_off_zero",
    "clear_off_from_nonzero",
    "refresh_only",
    "noop",
]


@dataclass(frozen=True)
class BrightnessPersistDecision:
    """What the poller should do when hardware brightness differs from last."""

    kind: BrightnessPersistKind
    track_brightness: int
    track_off: bool
    refresh_ui: bool = False


OffStatePersistKind = Literal[
    "ignore_power_forced_off",
    "recover_power_source_blank",
    "ignore_power_source_window",
    "mark_off",
    "clear_off",
    "noop",
]


@dataclass(frozen=True)
class OffStatePersistDecision:
    kind: OffStatePersistKind
    track_brightness: int
    track_off: bool
    refresh_ui: bool = False


def coerce_poll_int(value: object, *, default: int) -> int:
    try:
        return int(value)  # type: ignore[call-overload]
    except _BRIGHTNESS_COERCION_ERRORS:
        return int(default)


def normalize_brightness_to_config_scale(brightness: object) -> int:
    """Clamp brightness into KeyRGB's expected 0..50 range."""
    try:
        b = int(brightness)  # type: ignore[call-overload]
    except _BRIGHTNESS_COERCION_ERRORS:
        return 0
    return max(0, min(50, b))


def power_source_recovery_window_active(
    *,
    now: float,
    last_power_source_transition_at: float,
    window_s: float = POWER_SOURCE_RECOVERY_WINDOW_S,
) -> bool:
    if last_power_source_transition_at <= 0:
        return False
    return now - last_power_source_transition_at <= window_s


def hardware_poll_interval_s(
    *,
    now: float,
    last_power_source_transition_at: float,
    window_s: float = POWER_SOURCE_RECOVERY_WINDOW_S,
    fast_s: float = FAST_HARDWARE_POLL_INTERVAL_S,
    default_s: float = DEFAULT_HARDWARE_POLL_INTERVAL_S,
) -> float:
    if power_source_recovery_window_active(
        now=now,
        last_power_source_transition_at=last_power_source_transition_at,
        window_s=window_s,
    ):
        return fast_s
    return default_s


def should_attempt_power_source_blank_recovery(
    *,
    now: float,
    last_power_source_transition_at: float,
    last_recovery_at: float,
    any_forced_off: bool,
    configured_brightness_intent: int,
    window_s: float = POWER_SOURCE_RECOVERY_WINDOW_S,
    cooldown_s: float = POWER_SOURCE_RECOVERY_COOLDOWN_S,
) -> bool:
    if not power_source_recovery_window_active(
        now=now,
        last_power_source_transition_at=last_power_source_transition_at,
        window_s=window_s,
    ):
        return False
    if any_forced_off:
        return False
    if int(configured_brightness_intent) <= 0:
        return False
    if now - float(last_recovery_at) < cooldown_s:
        return False
    return True


def should_attempt_stable_zero_brightness_recovery(
    *,
    current_brightness: int,
    dim_temp_active: bool,
    any_forced_off: bool,
    configured_brightness_intent: int,
    now: float,
    last_recovery_at: float,
    cooldown_s: float = STABLE_ZERO_BRIGHTNESS_RECOVERY_COOLDOWN_S,
) -> bool:
    if int(current_brightness) != 0:
        return False
    if dim_temp_active:
        return False
    if any_forced_off:
        return False
    if int(configured_brightness_intent) <= 0:
        return False
    if now - float(last_recovery_at) < cooldown_s:
        return False
    return True


def classify_brightness_change_persist(
    *,
    current_brightness: int,
    current_off: bool,
    last_brightness: int | None,
    dim_temp_active: bool,
    dim_temp_target: int | None,
    user_forced_off: bool,
    power_forced_off: bool,
    idle_forced_off: bool,
    power_source_blank_recoverable: bool,
) -> BrightnessPersistDecision:
    """Pure policy for a hardware brightness change vs last tracked value.

    Callers supply whether power-source blank recovery is currently eligible
    (window + cooldown + intent already evaluated).
    """
    brightness = normalize_brightness_to_config_scale(current_brightness)
    off = bool(current_off)

    if dim_temp_active and dim_temp_target is not None:
        if brightness == 0 or off:
            return BrightnessPersistDecision(
                kind="ignore_dim_temp_transient",
                track_brightness=brightness,
                track_off=False,
            )

    zero_brightness_without_off_state = brightness == 0 and not off
    if brightness == 0 and (off or user_forced_off or power_forced_off or idle_forced_off):
        off = True

    if last_brightness is None or brightness == last_brightness:
        return BrightnessPersistDecision(
            kind="noop",
            track_brightness=brightness,
            track_off=off,
        )

    if dim_temp_active and dim_temp_target is not None:
        try:
            if int(brightness) == int(dim_temp_target):
                return BrightnessPersistDecision(
                    kind="track_dim_temp_match",
                    track_brightness=int(brightness),
                    track_off=off,
                )
        except _BRIGHTNESS_COERCION_ERRORS:
            pass

    if power_forced_off and brightness == 0:
        return BrightnessPersistDecision(
            kind="ignore_power_forced_zero",
            track_brightness=brightness,
            track_off=off,
        )

    if brightness == 0:
        if power_source_blank_recoverable:
            return BrightnessPersistDecision(
                kind="recover_power_source_blank",
                track_brightness=brightness,
                track_off=False,
                refresh_ui=True,
            )
        if zero_brightness_without_off_state:
            return BrightnessPersistDecision(
                kind="ignore_zero_without_off",
                track_brightness=brightness,
                track_off=False,
            )
        return BrightnessPersistDecision(
            kind="mark_off_zero",
            track_brightness=brightness,
            track_off=True,
            refresh_ui=True,
        )

    if last_brightness == 0 and not (user_forced_off or power_forced_off or idle_forced_off):
        return BrightnessPersistDecision(
            kind="clear_off_from_nonzero",
            track_brightness=brightness,
            track_off=False,
            refresh_ui=True,
        )

    return BrightnessPersistDecision(
        kind="refresh_only",
        track_brightness=brightness,
        track_off=off,
        refresh_ui=True,
    )


def classify_off_state_change_persist(
    *,
    current_brightness: int,
    current_off: bool,
    last_off_state: bool | None,
    power_forced_off: bool,
    user_forced_off: bool,
    idle_forced_off: bool,
    power_source_blank_recoverable: bool,
    power_source_window_active: bool,
) -> OffStatePersistDecision:
    brightness = normalize_brightness_to_config_scale(current_brightness)
    off = bool(current_off)

    if last_off_state is None or off == last_off_state:
        return OffStatePersistDecision(
            kind="noop",
            track_brightness=brightness,
            track_off=off,
        )

    if power_forced_off and off:
        return OffStatePersistDecision(
            kind="ignore_power_forced_off",
            track_brightness=brightness,
            track_off=off,
        )

    if off:
        if power_source_blank_recoverable:
            return OffStatePersistDecision(
                kind="recover_power_source_blank",
                track_brightness=brightness,
                track_off=False,
                refresh_ui=True,
            )
        if power_source_window_active:
            return OffStatePersistDecision(
                kind="ignore_power_source_window",
                track_brightness=brightness,
                track_off=False,
            )
        return OffStatePersistDecision(
            kind="mark_off",
            track_brightness=brightness,
            track_off=True,
            refresh_ui=True,
        )

    if not (user_forced_off or power_forced_off or idle_forced_off):
        return OffStatePersistDecision(
            kind="clear_off",
            track_brightness=brightness,
            track_off=False,
            refresh_ui=True,
        )

    return OffStatePersistDecision(
        kind="noop",
        track_brightness=brightness,
        track_off=off,
        refresh_ui=True,
    )
