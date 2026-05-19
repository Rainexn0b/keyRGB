from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import datetime

from src.core.brightness_layers import compose_power_source_brightness_overrides
from src.core.brightness_layers import resolve_scheduler_brightness_state
from src.core.utils.safe_attrs import _safe_getattr_or_none

from ._manager_config import read_power_management_config_bool
from ..policies.power_source_loop_policy import (
    ActivatePerkeyProfile,
    ActivatePowerMode,
    ApplyBrightness,
    PowerSourceLoopInputs,
    RestoreKeyboard,
    TurnOffKeyboard,
)
from ..system import PowerMode


logger = logging.getLogger(__name__)

_ACTIVE_PROFILE_LOOKUP_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_SAFE_INT_READ_ERRORS = (AttributeError, OSError, OverflowError, RuntimeError, TypeError, ValueError)
_CONTROLLER_ACTION_RUNTIME_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _run_controller_action_best_effort(*, kb_controller: object, method_name: str) -> None:
    try:
        method = getattr(kb_controller, method_name, None)
        if callable(method):
            method()
    except _CONTROLLER_ACTION_RUNTIME_ERRORS:  # @quality-exception exception-transparency: power-source controller actions cross a runtime backend boundary and must remain non-fatal for recoverable polling-loop failures
        logger.exception("Power-source controller action %s failed", method_name)


def _flag_attr_is_true(obj: object, name: str) -> bool:
    return _safe_getattr_or_none(obj, name) is True


def _power_management_enabled(config: object) -> bool:
    return read_power_management_config_bool(
        config,
        "power_management_enabled",
        "management_enabled",
        default=True,
        logger=logger,
    )


def build_power_source_loop_inputs(
    config: object,
    kb_controller: object,
    *,
    on_ac: bool,
    now_mono: float,
    get_power_mode_status_fn: Callable[[], object],
    get_active_perkey_profile_fn: Callable[[], str | None],
    safe_int_attr_fn: Callable[..., int],
) -> PowerSourceLoopInputs | None:
    config.reload()  # type: ignore[attr-defined]
    power_management_enabled = _power_management_enabled(config)
    if not power_management_enabled:
        return None

    current_brightness = safe_int_attr_fn(config, "brightness", default=0)
    try:
        status = get_power_mode_status_fn()
        active_power_mode = _safe_power_mode_from_status(status)
    except _ACTIVE_PROFILE_LOOKUP_ERRORS:
        active_power_mode = None
    try:
        active_perkey_profile_name = _safe_optional_profile_name(get_active_perkey_profile_fn())
    except _ACTIVE_PROFILE_LOOKUP_ERRORS:
        active_perkey_profile_name = None
    ac_enabled = bool(getattr(config, "ac_lighting_enabled", True))
    battery_enabled = bool(getattr(config, "battery_lighting_enabled", True))
    ac_power_mode = _safe_get_optional_power_mode(config, "ac_power_mode")
    battery_power_mode = _safe_get_optional_power_mode(config, "battery_power_mode")
    ac_perkey_profile_name = _safe_optional_profile_name(_safe_getattr_or_none(config, "ac_perkey_profile_name"))
    battery_perkey_profile_name = _safe_optional_profile_name(
        _safe_getattr_or_none(config, "battery_perkey_profile_name")
    )
    scheduler_state = resolve_scheduler_brightness_state(
        config,
        now=datetime.now(),
        power_management_enabled=power_management_enabled,
    )
    ac_brightness_override, battery_brightness_override = compose_power_source_brightness_overrides(
        ac_brightness_override=scheduler_state.ac_brightness_override,
        battery_brightness_override=scheduler_state.battery_brightness_override,
        scheduler_base_brightness=scheduler_state.active_base_brightness,
    )

    return PowerSourceLoopInputs(
        on_ac=bool(on_ac),
        now=float(now_mono),
        power_management_enabled=power_management_enabled,
        current_brightness=int(current_brightness),
        is_off=bool(getattr(kb_controller, "is_off", False)),
        active_power_mode=active_power_mode,
        active_perkey_profile_name=active_perkey_profile_name,
        ac_enabled=bool(ac_enabled),
        battery_enabled=bool(battery_enabled),
        ac_brightness_override=ac_brightness_override,
        battery_brightness_override=battery_brightness_override,
        ac_power_mode=ac_power_mode,
        battery_power_mode=battery_power_mode,
        ac_perkey_profile_name=ac_perkey_profile_name,
        battery_perkey_profile_name=battery_perkey_profile_name,
        battery_saver_enabled=bool(getattr(config, "battery_saver_enabled", False)),
        battery_saver_brightness=int(safe_int_attr_fn(config, "battery_saver_brightness", default=25)),
    )


def _safe_get_optional_power_mode(config: object, attr_name: str) -> PowerMode | None:
    value = _safe_getattr_or_none(config, attr_name)
    return _safe_power_mode_from_value(value)


def _safe_power_mode_from_status(status: object) -> PowerMode | None:
    supported = bool(_safe_getattr_or_none(status, "supported"))
    if not supported:
        return None
    return _safe_power_mode_from_value(_safe_getattr_or_none(status, "mode"))


def _safe_power_mode_from_value(value: object) -> PowerMode | None:
    if isinstance(value, PowerMode) and value != PowerMode.UNKNOWN:
        return value
    normalized = str(value or "").strip().lower()
    if not normalized:
        return None
    try:
        mode = PowerMode(normalized)
    except ValueError:
        return None
    return mode if mode != PowerMode.UNKNOWN else None


def _safe_optional_profile_name(value: object) -> str | None:
    try:
        normalized = str(value or "").strip()
    except _ACTIVE_PROFILE_LOOKUP_ERRORS:
        return None
    return normalized or None


def apply_power_source_actions(
    *,
    kb_controller: object,
    actions: Iterable[object],
    apply_brightness: Callable[[int], None],
    activate_power_mode: Callable[[PowerMode], None],
    activate_perkey_profile: Callable[[str], None],
) -> None:
    for action in actions:
        if isinstance(action, TurnOffKeyboard):
            _run_controller_action_best_effort(kb_controller=kb_controller, method_name="turn_off")
        elif isinstance(action, RestoreKeyboard):
            _run_controller_action_best_effort(kb_controller=kb_controller, method_name="restore")
        elif isinstance(action, ApplyBrightness):
            apply_brightness(int(action.brightness))
        elif isinstance(action, ActivatePowerMode):
            try:
                activate_power_mode(action.mode)
            except _CONTROLLER_ACTION_RUNTIME_ERRORS:
                logger.exception("Power-source mode activation failed for %s", action.mode.value)
        elif isinstance(action, ActivatePerkeyProfile):
            try:
                activate_perkey_profile(action.profile_name)
            except _CONTROLLER_ACTION_RUNTIME_ERRORS:
                logger.exception("Power-source profile activation failed for %s", action.profile_name)


def is_intentionally_off(*, kb_controller: object, config: object, safe_int_attr_fn: Callable[..., int]) -> bool:
    if _flag_attr_is_true(kb_controller, "user_forced_off"):
        return True

    if _flag_attr_is_true(kb_controller, "_user_forced_off"):
        return True

    try:
        return safe_int_attr_fn(config, "brightness", default=0) == 0
    except _SAFE_INT_READ_ERRORS:
        return False
