"""Apply per-key and uniform-none static lighting modes.

Extracted from ``_lighting_controller_helpers.py`` (WS1 / A6 slice 1).
Imports shared diagnostic helpers from the parent helpers module; the parent
re-exports these apply functions so existing call sites stay stable.
"""

from __future__ import annotations

from keyrgb.core.effects.perkey_animation import restore_hidden_per_key_rows_once
from keyrgb.core.utils.safe_attrs import safe_int_attr
from keyrgb.tray.idle_power_state import (
    clear_idle_power_state_field,
    read_idle_power_state_optional_bool_field,
    read_idle_power_state_optional_int_field,
)
from keyrgb.tray.protocols import LightingTrayProtocol


def apply_perkey_mode(
    tray: LightingTrayProtocol,
    *,
    brightness_override: int | None = None,
    reassert_user_mode: bool = True,
) -> None:
    # Local import avoids import cycle: helpers re-exports this module.
    from keyrgb.core.backends.base import normalize_backend_capabilities
    from keyrgb.tray.controllers import _lighting_controller_helpers as helpers

    if not normalize_backend_capabilities(tray.backend_caps).per_key:
        apply_uniform_none_mode(tray, brightness_override=brightness_override)
        return

    def _clear_hidden_restore_hints() -> None:
        clear_idle_power_state_field(
            tray,
            attr_name="_hidden_perkey_restore_brightness_hint",
            state_name="hidden_perkey_restore_brightness_hint",
            value=None,
        )
        clear_idle_power_state_field(
            tray,
            attr_name="_hidden_perkey_restore_device_off_hint",
            state_name="hidden_perkey_restore_device_off_hint",
            value=None,
        )

    should_reassert_user_mode = bool(reassert_user_mode) or helpers._perkey_backend_requires_reassert(tray)
    should_pre_enable_user_mode = bool(reassert_user_mode)
    if brightness_override is not None:
        effective_brightness = helpers._coerce_brightness_override(brightness_override)
    else:
        effective_brightness = safe_int_attr(tray.config, "brightness", default=0)
    if int(effective_brightness) == 0:
        if should_reassert_user_mode:
            tray.engine.stop()
        tray.engine.turn_off()
        tray.is_off = True
        return

    helpers._set_engine_attr_best_effort(
        tray,
        "per_key_colors",
        helpers._config_per_key_colors_ref(tray.config),
        error_msg="Failed to apply per-key colors to engine: %s",
        fallback=None,
    )
    helpers._set_engine_attr_best_effort(
        tray,
        "per_key_brightness",
        safe_int_attr(
            tray.config,
            "perkey_brightness",
            default=safe_int_attr(tray.config, "brightness", default=0),
        ),
        error_msg="Failed to apply per-key brightness to engine: %s",
        fallback=None,
    )
    if (
        should_reassert_user_mode
        and not should_pre_enable_user_mode
        and restore_hidden_per_key_rows_once(
            kb=tray.engine.kb,
            kb_lock=tray.engine.kb_lock,
            color_map=tray.config.per_key_colors,
            brightness=int(effective_brightness),
            known_brightness=read_idle_power_state_optional_int_field(
                tray,
                attr_name="_hidden_perkey_restore_brightness_hint",
                state_name="hidden_perkey_restore_brightness_hint",
                default=None,
            ),
            known_is_off=read_idle_power_state_optional_bool_field(
                tray,
                attr_name="_hidden_perkey_restore_device_off_hint",
                state_name="hidden_perkey_restore_device_off_hint",
                default=None,
            ),
        )
    ):
        _clear_hidden_restore_hints()
        tray.is_off = False
        return

    _clear_hidden_restore_hints()

    if should_reassert_user_mode:
        tray.engine.stop()

    with tray.engine.kb_lock:
        if should_pre_enable_user_mode:
            enable_user_mode = getattr(tray.engine.kb, "enable_user_mode", None)
            if callable(enable_user_mode):
                try:
                    enable_user_mode(brightness=effective_brightness, save=True)
                except TypeError:
                    try:
                        enable_user_mode(brightness=effective_brightness)
                    except helpers._RECOVERABLE_ENABLE_USER_MODE_EXCEPTIONS as exc:
                        helpers._log_tray_exception(tray, "Failed to enable per-key user mode: %s", exc)
                except helpers._RECOVERABLE_ENABLE_USER_MODE_EXCEPTIONS as exc:
                    helpers._log_tray_exception(tray, "Failed to enable per-key user mode: %s", exc)
        tray.engine.kb.set_key_colors(
            tray.config.per_key_colors,
            brightness=effective_brightness,
            enable_user_mode=should_reassert_user_mode,
        )

    tray.is_off = False


def restore_hidden_perkey_rows_from_recovery_hint(
    tray: LightingTrayProtocol,
    *,
    brightness_override: int | None = None,
) -> bool:
    """Restore per-key rows during an explicit hidden-blank recovery hint.

    The hardware poller supplies the brightness/off observations that made it
    classify the controller as blank-but-not-off.  Avoid requerying the device
    here: sleeping ITE controllers may wake into their saved startup effect if
    polled unnecessarily.  Row data is written before brightness is raised and
    no user-mode command or effect restart is issued, except for the opt-in
    ``KEYRGB_RECOVERY_USER_MODE_SAVE=1`` experiment, which saves the restored
    scene once so the firmware's first-keypress wake ramp targets current state.
    """

    from keyrgb.core.backends.base import normalize_backend_capabilities
    from keyrgb.tray.controllers import _lighting_controller_helpers as helpers

    if not normalize_backend_capabilities(tray.backend_caps).per_key:
        return False

    known_brightness = read_idle_power_state_optional_int_field(
        tray,
        attr_name="_hidden_perkey_restore_brightness_hint",
        state_name="hidden_perkey_restore_brightness_hint",
        default=None,
    )
    known_is_off = read_idle_power_state_optional_bool_field(
        tray,
        attr_name="_hidden_perkey_restore_device_off_hint",
        state_name="hidden_perkey_restore_device_off_hint",
        default=None,
    )
    if known_brightness is None or known_is_off is None:
        return False
    if int(known_brightness) > 0 or bool(known_is_off):
        return False

    if brightness_override is not None:
        effective_brightness = helpers._coerce_brightness_override(brightness_override)
    else:
        effective_brightness = safe_int_attr(tray.config, "brightness", default=0)
    if int(effective_brightness) <= 0:
        return False

    color_map = helpers._config_per_key_colors_ref(tray.config)
    if not color_map:
        return False

    return restore_hidden_per_key_rows_once(
        kb=tray.engine.kb,
        kb_lock=tray.engine.kb_lock,
        color_map=color_map,
        brightness=int(effective_brightness),
        known_brightness=int(known_brightness),
        known_is_off=bool(known_is_off),
    )


def apply_uniform_none_mode(tray: LightingTrayProtocol, *, brightness_override: int | None = None) -> None:
    from keyrgb.tray.controllers import _lighting_controller_helpers as helpers

    tray.engine.stop()
    if brightness_override is not None:
        effective_brightness = helpers._coerce_brightness_override(brightness_override)
    else:
        effective_brightness = safe_int_attr(tray.config, "brightness", default=0)
    if int(effective_brightness) == 0:
        tray.engine.turn_off()
        tray.is_off = True
        return

    helpers.clear_engine_perkey_state(tray)

    with tray.engine.kb_lock:
        tray.engine.kb.set_color(tray.config.color, brightness=effective_brightness)

    tray.is_off = False
