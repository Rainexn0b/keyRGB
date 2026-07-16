from __future__ import annotations

from collections.abc import Callable

from src.core.utils.safe_attrs import safe_int_attr
from src.tray.idle_power_state import set_last_brightness
from src.tray.protocols import LightingTrayProtocol

from ._lighting_controller_helpers import (
    _log_tray_exception,
    get_effect_name,
    is_reactive_effect,
    is_software_effect,
    sync_reactive_effect_brightness_state,
    try_log_event,
)


# Layered brightness apply crosses config/engine/UI; no map LookupError expected.
_BRIGHTNESS_LAYER_RUNTIME_EXCEPTIONS = (AttributeError, OSError, RuntimeError, TypeError, ValueError)


def apply_layered_brightness_update(
    tray: LightingTrayProtocol,
    *,
    source: str,
    base_brightness: int | None,
    reactive_brightness: int | None,
    reactive_source_label: str | None = None,
    start_current_effect: Callable[[LightingTrayProtocol], None],
) -> None:
    if base_brightness is None and reactive_brightness is None:
        return

    if base_brightness is not None and int(base_brightness) > 0:
        set_last_brightness(tray, int(base_brightness))

    try_log_event(
        tray,
        source,
        "apply_brightness",
        base=base_brightness,
        reactive=reactive_brightness,
    )

    effect = get_effect_name(tray)
    is_sw_effect = is_software_effect(effect)
    is_reactive = is_reactive_effect(effect)
    is_perkey = effect == "perkey"

    prev_cfg_brightness = safe_int_attr(tray.config, "brightness", default=0)
    fade_down = bool(base_brightness is not None and int(base_brightness) < prev_cfg_brightness)
    fade_s = 0.12 if base_brightness is not None and int(base_brightness) <= 0 else 0.25

    if is_reactive:
        if base_brightness is not None:
            tray.config.perkey_brightness = int(base_brightness)
            tray.config.brightness = int(base_brightness)
        if reactive_brightness is not None:
            tray.config.reactive_brightness = int(reactive_brightness)
        sync_reactive_effect_brightness_state(
            tray,
            source=str(reactive_source_label or source),
            base_brightness=base_brightness,
            reactive_brightness=reactive_brightness,
            fade=fade_down,
            fade_duration_s=fade_s,
        )
        tray._refresh_ui()
        return

    if reactive_brightness is not None:
        tray.config.reactive_brightness = int(reactive_brightness)

    if base_brightness is None:
        return

    brightness = int(base_brightness)

    if is_perkey:
        tray.config.perkey_brightness = brightness
        tray.config.brightness = brightness
        try:
            tray.engine.per_key_brightness = brightness
        except _BRIGHTNESS_LAYER_RUNTIME_EXCEPTIONS as exc:
            _log_tray_exception(tray, f"Failed to sync {source} per-key brightness state: %s", exc)
        tray.engine.set_brightness(
            tray.config.brightness,
            apply_to_hardware=True,
            fade=fade_down,
            fade_duration_s=fade_s,
        )
        tray.is_off = False
        tray._refresh_ui()
        return

    tray.config.brightness = brightness
    tray.engine.set_brightness(
        tray.config.brightness,
        apply_to_hardware=not is_sw_effect,
        fade=fade_down,
        fade_duration_s=fade_s,
    )
    if not bool(getattr(tray, "is_off", False)) and not is_sw_effect:
        start_current_effect(tray)
    tray._refresh_ui()
