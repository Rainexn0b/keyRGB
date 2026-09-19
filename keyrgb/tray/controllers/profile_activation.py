"""Tray-owned wiring for core profile activation.

Core profile activation accepts explicit hooks only. This module is the tray
boundary that supplies those hooks from tray state and public facades.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import cast

from keyrgb.core.backends.base import normalize_backend_capabilities
from keyrgb.core.lighting_layers import uniform_color_from_per_key_map
from keyrgb.core.profile import profiles as core_profiles, runtime_activation as profile_runtime_activation
from keyrgb.tray.controllers.runtime_coordination import run_tray_transition
from keyrgb.tray.deck_pipeline import hardware_apply_deferred
from keyrgb.tray.idle_power_state import (
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


def _sync_uniform_color_for_zoned_backend(tray: object, config: object, colors: object) -> None:
    """Sync ``config.color`` from activated profile colors on zoned-only backends.

    Zone devices render per-key maps by averaging them to one uniform color, so
    the uniform software-static render must derive the same color. Runs inside
    the apply hook, before any runtime effect start, and therefore also while
    forced-off suppression holds the deck dark.
    """

    try:
        caps = normalize_backend_capabilities(getattr(tray, "backend_caps", None))
    except _PROFILE_ACTIVATION_STATE_ERRORS:
        return
    if not (caps.zoned and not caps.per_key):
        return
    uniform = uniform_color_from_per_key_map(colors)
    if uniform is None:
        return
    try:
        config.color = uniform  # type: ignore[attr-defined]
    except _PROFILE_ACTIVATION_STATE_ERRORS:
        return


def _make_zoned_sync_apply_hook(tray: object) -> Callable[..., None]:
    def _apply(config, colors, *, secondary_lighting: Mapping[str, object] | None = None) -> None:
        core_profiles.apply_profile_to_config(config, colors, secondary_lighting=secondary_lighting)
        _sync_uniform_color_for_zoned_backend(tray, config, colors)

    return _apply


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
        apply_profile_to_config_fn=_make_zoned_sync_apply_hook(tray),
        load_secondary_lighting_fn=core_profiles.load_secondary_lighting,
        # Run-time suppression facade: suppress hardware/effect application while
        # ANY forced-off owner (user, power/suspend/lid, or idle/screen-off)
        # holds the deck dark, but still persist profile intent and marker.
        is_power_forced_off_fn=lambda: hardware_apply_deferred(tray),
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
