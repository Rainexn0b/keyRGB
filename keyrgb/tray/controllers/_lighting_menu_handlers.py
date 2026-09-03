from __future__ import annotations

from collections.abc import Callable

from keyrgb.core.effects.catalog import resolve_effect_name_for_backend
from keyrgb.core.utils import safe_attrs
from keyrgb.tray.controllers import _lighting_controller_helpers as lighting_controller_helpers
from keyrgb.tray.controllers._brightness_layer import apply_layered_brightness_update
from keyrgb.tray.protocols import LightingTrayProtocol

_LOCAL_COMPATIBILITY_FALLBACK_EXCEPTIONS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)


def on_speed_clicked_impl(
    tray: LightingTrayProtocol,
    item: object,
    *,
    start_current_effect: Callable[[LightingTrayProtocol], object],
    log_boundary_exception: Callable[[LightingTrayProtocol, str, Exception], None],
) -> None:
    speed = lighting_controller_helpers.parse_menu_int(item)
    if speed is None:
        return

    lighting_controller_helpers.try_log_event(
        tray,
        "menu",
        "set_speed",
        old=safe_attrs.safe_int_attr(tray.config, "speed", default=0),
        new=int(speed),
    )

    # Save globally and as a per-effect override so each effect remembers its speed.
    tray.config.speed = speed
    from keyrgb.tray.deck_pipeline import hardware_apply_deferred

    defer_hardware_apply = hardware_apply_deferred(tray)
    effect = lighting_controller_helpers.get_effect_name(tray)
    if defer_hardware_apply:
        # The engine may still describe the last physically running effect.
        # Speed intent belongs to the normalized config effect while the deck
        # is dark, not to that stale render cache.
        effect = resolve_effect_name_for_backend(
            safe_attrs.safe_str_attr(tray.config, "effect", default="none") or "none",
            getattr(tray, "backend", None),
        )
    if effect and effect not in {"none", "perkey"}:
        tray.config.set_effect_speed(effect, speed)
    if not defer_hardware_apply:
        is_loop = lighting_controller_helpers.is_software_effect(
            effect
        ) or lighting_controller_helpers.is_reactive_effect(effect)
        if is_loop:
            # SW/reactive loops read engine.speed on every frame - update in-place
            # without restarting the loop (avoids flicker and state loss).
            try:
                tray.engine.speed = speed
            except _LOCAL_COMPATIBILITY_FALLBACK_EXCEPTIONS as exc:
                log_boundary_exception(tray, "Failed to update engine speed in place: %s", exc)
                start_current_effect(tray)
        else:
            start_current_effect(tray)
    tray._update_menu()


def on_brightness_clicked_impl(
    tray: LightingTrayProtocol,
    item: object,
    *,
    start_current_effect: Callable[[LightingTrayProtocol], object],
) -> None:
    brightness = lighting_controller_helpers.parse_menu_int(item)
    if brightness is None:
        return

    from keyrgb.tray.deck_pipeline import hardware_apply_deferred

    apply_layered_brightness_update(
        tray,
        source="menu",
        base_brightness=int(brightness * 5),
        reactive_brightness=None,
        reactive_source_label="tray brightness",
        start_current_effect=start_current_effect,
        defer_hardware_apply=hardware_apply_deferred(tray),
    )
