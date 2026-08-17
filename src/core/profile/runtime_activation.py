from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TypeAlias

_RUNTIME_ACTIVATION_STATE_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)
PerKeyCoord: TypeAlias = tuple[int, int]
PerKeyColor: TypeAlias = tuple[int, int, int]
PerKeyColorMap: TypeAlias = dict[PerKeyCoord, PerKeyColor]
SecondaryLightingPayload: TypeAlias = Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ProfileActivationResult:
    """Outcome of applying one profile into shared config state."""

    name: str
    colors: PerKeyColorMap
    secondary_lighting: SecondaryLightingPayload | None
    runtime_applied: bool
    used_in_place_transition: bool


def activate_perkey_profile_runtime(
    config: object,
    profile_name: str,
    *,
    set_active_profile_fn: Callable[[str], str],
    load_per_key_colors_fn: Callable[[str | None], Mapping[PerKeyCoord, PerKeyColor]],
    apply_profile_to_config_fn: Callable[..., None],
    load_secondary_lighting_fn: Callable[[str | None], SecondaryLightingPayload | None] | None = None,
    is_power_forced_off_fn: Callable[[], bool] | None = None,
    set_is_off_fn: Callable[[bool], None] | None = None,
    store_secondary_lighting_fn: Callable[[SecondaryLightingPayload], None] | None = None,
    apply_runtime_transition_fn: Callable[[], bool] | None = None,
    start_current_effect_fn: Callable[[], object] | None = None,
    update_icon_fn: Callable[[], None] | None = None,
    update_menu_fn: Callable[[], None] | None = None,
    mark_power_source_transition_fn: Callable[[str, float], None] | None = None,
    mark_power_source_transition: bool = False,
    refresh_menu: bool = True,
    monotonic_fn: Callable[[], float] = time.monotonic,
) -> ProfileActivationResult:
    """Activate one per-key profile through explicit application hooks.

    Core owns config application order only. Runtime lighting and UI side effects
    are supplied by callers; this module does not resolve private tray methods or
    tray-owned attributes by name.
    """

    name = set_active_profile_fn(profile_name)
    colors = dict(load_per_key_colors_fn(name) or {})
    secondary_lighting = load_secondary_lighting_fn(name) if load_secondary_lighting_fn is not None else None

    if secondary_lighting is not None and store_secondary_lighting_fn is not None:
        store_secondary_lighting_fn(secondary_lighting)

    if secondary_lighting is None:
        apply_profile_to_config_fn(config, colors)
    else:
        apply_profile_to_config_fn(config, colors, secondary_lighting=secondary_lighting)

    if mark_power_source_transition and mark_power_source_transition_fn is not None:
        try:
            changed_at = float(monotonic_fn())
        except _RUNTIME_ACTIVATION_STATE_EXCEPTIONS:
            changed_at = None
        if changed_at is not None:
            mark_power_source_transition_fn(name, changed_at)

    power_forced_off = False
    if is_power_forced_off_fn is not None:
        try:
            power_forced_off = bool(is_power_forced_off_fn())
        except _RUNTIME_ACTIVATION_STATE_EXCEPTIONS:
            power_forced_off = False

    used_in_place_transition = False
    runtime_applied = False
    if not power_forced_off:
        if set_is_off_fn is not None:
            set_is_off_fn(False)
        if apply_runtime_transition_fn is not None:
            try:
                used_in_place_transition = bool(apply_runtime_transition_fn())
            except _RUNTIME_ACTIVATION_STATE_EXCEPTIONS:
                used_in_place_transition = False
        if not used_in_place_transition and start_current_effect_fn is not None:
            start_current_effect_fn()
        runtime_applied = True

    if update_icon_fn is not None:
        update_icon_fn()
    if bool(refresh_menu) and update_menu_fn is not None:
        update_menu_fn()

    return ProfileActivationResult(
        name=name,
        colors=colors,
        secondary_lighting=secondary_lighting,
        runtime_applied=runtime_applied,
        used_in_place_transition=used_in_place_transition,
    )
