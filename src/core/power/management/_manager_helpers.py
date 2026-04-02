from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from typing import Any

from src.core.utils.safe_attrs import _safe_getattr_or_none

from ..policies.power_source_loop_policy import (
    ApplyBrightness,
    PowerSourceLoopInputs,
    RestoreKeyboard,
    TurnOffKeyboard,
)


logger = logging.getLogger(__name__)

_ACTIVE_PROFILE_LOOKUP_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
_SAFE_INT_READ_ERRORS = (AttributeError, OSError, OverflowError, RuntimeError, TypeError, ValueError)


def _run_controller_action_best_effort(*, kb_controller: Any, method_name: str) -> None:
    try:
        method = getattr(kb_controller, method_name, None)
        if callable(method):
            method()
    except Exception:  # @quality-exception exception-transparency: power-source controller actions cross a runtime backend boundary and must remain non-fatal for the polling loop
        logger.exception("Power-source controller action %s failed", method_name)


def _flag_attr_is_true(obj: Any, name: str) -> bool:
    return _safe_getattr_or_none(obj, name) is True


def build_power_source_loop_inputs(
    config: Any,
    kb_controller: Any,
    *,
    on_ac: bool,
    now_mono: float,
    get_active_profile_fn: Callable[[], str],
    safe_int_attr_fn: Callable[..., int],
) -> PowerSourceLoopInputs | None:
    config.reload()
    if not bool(getattr(config, "power_management_enabled", True)):
        return None

    current_brightness = safe_int_attr_fn(config, "brightness", default=0)
    ac_enabled = bool(getattr(config, "ac_lighting_enabled", True))
    battery_enabled = bool(getattr(config, "battery_lighting_enabled", True))
    ac_brightness_override = getattr(config, "ac_lighting_brightness", None)
    battery_brightness_override = getattr(config, "battery_lighting_brightness", None)

    try:
        active_profile = get_active_profile_fn()
    except _ACTIVE_PROFILE_LOOKUP_ERRORS:
        active_profile = ""

    if active_profile in {"dim", "dark"}:
        ac_enabled = True
        battery_enabled = True
        ac_brightness_override = None
        battery_brightness_override = None

    return PowerSourceLoopInputs(
        on_ac=bool(on_ac),
        now=float(now_mono),
        power_management_enabled=bool(getattr(config, "power_management_enabled", True)),
        current_brightness=int(current_brightness),
        is_off=bool(getattr(kb_controller, "is_off", False)),
        ac_enabled=bool(ac_enabled),
        battery_enabled=bool(battery_enabled),
        ac_brightness_override=ac_brightness_override,
        battery_brightness_override=battery_brightness_override,
        battery_saver_enabled=bool(getattr(config, "battery_saver_enabled", False)),
        battery_saver_brightness=int(safe_int_attr_fn(config, "battery_saver_brightness", default=25)),
    )


def apply_power_source_actions(
    *,
    kb_controller: Any,
    actions: Iterable[object],
    apply_brightness: Callable[[int], None],
) -> None:
    for action in actions:
        if isinstance(action, TurnOffKeyboard):
            _run_controller_action_best_effort(kb_controller=kb_controller, method_name="turn_off")
        elif isinstance(action, RestoreKeyboard):
            _run_controller_action_best_effort(kb_controller=kb_controller, method_name="restore")
        elif isinstance(action, ApplyBrightness):
            apply_brightness(int(action.brightness))


def is_intentionally_off(*, kb_controller: Any, config: Any, safe_int_attr_fn: Callable[..., int]) -> bool:
    if _flag_attr_is_true(kb_controller, "user_forced_off"):
        return True

    if _flag_attr_is_true(kb_controller, "_user_forced_off"):
        return True

    try:
        return safe_int_attr_fn(config, "brightness", default=0) == 0
    except _SAFE_INT_READ_ERRORS:
        return False
