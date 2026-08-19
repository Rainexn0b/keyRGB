"""Tray-owned wiring for core profile activation.

Core profile activation accepts explicit hooks only. This module is the tray
boundary that supplies those hooks from tray state and public facades.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import cast

from keyrgb.core.profile import profiles as core_profiles, runtime_activation as profile_runtime_activation
from keyrgb.tray.controllers.runtime_coordination import run_tray_transition
from keyrgb.tray.idle_power_state import (
    read_idle_power_state_bool_field,
    set_idle_power_state_field,
)

_PROFILE_ACTIVATION_STATE_ERRORS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


def _resolve_tray_callable(tray: object, name: str) -> Callable[..., object] | None:
    try:
        instance_callback = vars(tray).get(name)
    except TypeError:
        instance_callback = None
    if callable(instance_callback):
        return cast(Callable[..., object], instance_callback)

    attr = getattr(tray, name, None)
    if callable(attr):
        return cast(Callable[..., object], attr)
    return None


def _as_void_callback(fn: Callable[..., object]) -> Callable[[], None]:
    def _wrapped() -> None:
        fn()

    return _wrapped


def _store_active_secondary_lighting(tray: object, payload: Mapping[str, object]) -> None:
    try:
        vars(tray)["_active_secondary_lighting"] = payload
    except (AttributeError, TypeError):
        return


def _mark_power_source_transition(tray: object, profile_name: str, changed_at: float) -> None:
    try:
        tray._last_power_source_transition_at = float(changed_at)  # type: ignore[attr-defined]
    except _PROFILE_ACTIVATION_STATE_ERRORS:
        pass
    set_idle_power_state_field(
        tray,
        attr_name="_last_power_source_transition_at",
        state_name="last_power_source_transition_at",
        value=float(changed_at),
    )

    profile_name_text = str(profile_name)
    try:
        tray._last_power_source_transition_profile_name = profile_name_text  # type: ignore[attr-defined]
    except _PROFILE_ACTIVATION_STATE_ERRORS:
        pass
    set_idle_power_state_field(
        tray,
        attr_name="_last_power_source_transition_profile_name",
        state_name="last_power_source_transition_profile_name",
        value=profile_name_text,
    )


def activate_perkey_profile_on_tray(
    tray: object,
    profile_name: str,
    *,
    mark_power_source_transition: bool = False,
    refresh_menu: bool = True,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> profile_runtime_activation.ProfileActivationResult:
    """Activate a profile against tray config/runtime through explicit hooks."""

    config = getattr(tray, "config", None)
    start_current_effect = _resolve_tray_callable(tray, "_start_current_effect")
    update_icon = _resolve_tray_callable(tray, "_update_icon")
    update_menu = _resolve_tray_callable(tray, "_update_menu")
    apply_transition = _resolve_tray_callable(tray, "_apply_power_source_perkey_profile_transition")

    def _set_is_off(value: bool) -> None:
        try:
            tray.is_off = bool(value)  # type: ignore[attr-defined]
        except _PROFILE_ACTIVATION_STATE_ERRORS:
            return

    return profile_runtime_activation.activate_perkey_profile_runtime(
        config,
        profile_name,
        set_active_profile_fn=core_profiles.set_active_profile,
        load_per_key_colors_fn=core_profiles.load_per_key_colors,
        apply_profile_to_config_fn=core_profiles.apply_profile_to_config,
        load_secondary_lighting_fn=core_profiles.load_secondary_lighting,
        is_power_forced_off_fn=lambda: read_idle_power_state_bool_field(
            tray,
            attr_name="_power_forced_off",
            state_name="power_forced_off",
            default=False,
        ),
        set_is_off_fn=_set_is_off,
        store_secondary_lighting_fn=lambda payload: _store_active_secondary_lighting(tray, payload),
        apply_runtime_transition_fn=((lambda: bool(apply_transition())) if apply_transition is not None else None),
        start_current_effect_fn=((lambda: start_current_effect()) if start_current_effect is not None else None),
        update_icon_fn=(_as_void_callback(update_icon) if update_icon is not None else None),
        update_menu_fn=(_as_void_callback(update_menu) if update_menu is not None else None),
        mark_power_source_transition_fn=(
            (lambda name, changed_at: _mark_power_source_transition(tray, name, changed_at))
            if mark_power_source_transition
            else None
        ),
        mark_power_source_transition=mark_power_source_transition,
        refresh_menu=refresh_menu,
        monotonic_fn=monotonic_fn,
    )


def activate_perkey_profile(tray: object, profile_name: str) -> None:
    """Menu/public tray entrypoint for profile activation."""

    run_tray_transition(
        tray,
        lambda: activate_perkey_profile_on_tray(tray, profile_name),
    )
