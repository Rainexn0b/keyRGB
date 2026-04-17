from __future__ import annotations

import logging
from typing import Optional

from src.core.effects import catalog as effects_catalog
from src.core.utils import exceptions as core_exceptions
from src.core.utils import safe_attrs
from src.tray.controllers import _lighting_controller_helpers as lighting_controller_helpers
from src.tray.controllers._power import _lighting_power_policy as lighting_power_policy
from src.tray.controllers._power import _lighting_power_state as lighting_power_state
from src.tray.controllers import software_target_controller
from src.tray.protocols import LightingTrayProtocol


SW_EFFECTS = effects_catalog.SW_EFFECTS_SET
resolve_effect_name_for_backend = effects_catalog.resolve_effect_name_for_backend
safe_int_attr = safe_attrs.safe_int_attr
safe_str_attr = safe_attrs.safe_str_attr
apply_brightness_from_power_policy_impl = lighting_power_policy.apply_brightness_from_power_policy_impl
power_restore_impl = lighting_power_state.power_restore_impl
power_turn_off_impl = lighting_power_state.power_turn_off_impl
turn_off_impl = lighting_power_state.turn_off_impl
turn_on_impl = lighting_power_state.turn_on_impl
apply_perkey_mode = lighting_controller_helpers.apply_perkey_mode
apply_uniform_none_mode = lighting_controller_helpers.apply_uniform_none_mode
clear_engine_perkey_state = lighting_controller_helpers.clear_engine_perkey_state
ensure_device_best_effort = lighting_controller_helpers.ensure_device_best_effort
get_effect_name = lighting_controller_helpers.get_effect_name
is_reactive_effect = lighting_controller_helpers.is_reactive_effect
is_software_effect = lighting_controller_helpers.is_software_effect
parse_menu_int = lighting_controller_helpers.parse_menu_int
set_engine_perkey_from_config_for_sw_effect = lighting_controller_helpers.set_engine_perkey_from_config_for_sw_effect
try_log_event = lighting_controller_helpers.try_log_event
run_diagnostic_boundary = lighting_controller_helpers._run_diagnostic_boundary
restore_secondary_software_targets = software_target_controller.restore_secondary_software_targets
software_effect_target_routes_aux_devices = software_target_controller.software_effect_target_routes_aux_devices
turn_off_secondary_software_targets = software_target_controller.turn_off_secondary_software_targets
is_device_disconnected = core_exceptions.is_device_disconnected
is_permission_denied = core_exceptions.is_permission_denied

logger = logging.getLogger(__name__)


_LOCAL_COMPATIBILITY_FALLBACK_EXCEPTIONS = (
    AttributeError,
    OSError,
    RuntimeError,
    TypeError,
    ValueError,
)
_START_CURRENT_EFFECT_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_TRAY_LOGGER_CALLBACK_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _coerce_brightness_override(brightness_override: object, *, default: int) -> int:
    try:
        value = int(brightness_override)  # type: ignore[call-overload]
    except (TypeError, ValueError, OverflowError):
        return default
    return max(0, min(50, value))


def _log_boundary_exception(tray: LightingTrayProtocol, msg: str, exc: Exception) -> None:
    def _recover_tray_logging(log_exc: Exception) -> None:
        logger.exception("Tray exception logger failed while logging boundary: %s", log_exc)
        logger.error(msg, exc, exc_info=(type(exc), exc, exc.__traceback__))

    run_diagnostic_boundary(
        lambda: tray._log_exception(msg, exc),
        runtime_exceptions=_TRAY_LOGGER_CALLBACK_EXCEPTIONS,
        on_recoverable=_recover_tray_logging,
    )


def start_current_effect(
    tray: LightingTrayProtocol,
    *,
    brightness_override: Optional[int] = None,
    fade_in: bool = False,
    fade_in_duration_s: float = 0.25,
) -> None:
    """Start the currently selected effect.

    This is best-effort and must never crash the tray.
    """

    try:
        ensure_device_best_effort(tray)

        target_brightness = safe_int_attr(tray.config, "brightness", default=0)
        start_brightness = target_brightness
        if brightness_override is not None:
            start_brightness = _coerce_brightness_override(brightness_override, default=target_brightness)

        raw_effect = safe_str_attr(tray.config, "effect", default="none") or "none"
        effect = resolve_effect_name_for_backend(raw_effect, getattr(tray, "backend", None))
        if effect != raw_effect:
            tray.config.effect = effect
        if effect == "perkey":
            apply_perkey_mode(tray, brightness_override=start_brightness)
            if software_effect_target_routes_aux_devices(tray):
                restore_secondary_software_targets(tray)
            if fade_in and target_brightness > start_brightness and target_brightness > 0:
                tray.engine.set_brightness(
                    target_brightness,
                    apply_to_hardware=True,
                    fade=True,
                    fade_duration_s=float(fade_in_duration_s),
                )
            return

        if effect == "none":
            apply_uniform_none_mode(tray, brightness_override=start_brightness)
            if software_effect_target_routes_aux_devices(tray):
                restore_secondary_software_targets(tray)
            if fade_in and target_brightness > start_brightness and target_brightness > 0:
                tray.engine.set_brightness(
                    target_brightness,
                    apply_to_hardware=True,
                    fade=True,
                    fade_duration_s=float(fade_in_duration_s),
                )
            return

        # Prepare per-key state in case the effect is a software effect that needs it.
        # This handles cases like 'reactive_ripple' running on startup where the menu logic hasn't run.
        if effect in SW_EFFECTS:
            set_engine_perkey_from_config_for_sw_effect(tray)
        else:
            clear_engine_perkey_state(tray)

        # When a fade-in is planned, decide the ramp strategy based on
        # whether the effect runs its own render loop.
        _will_fade = fade_in and target_brightness > start_brightness and target_brightness > 0
        is_loop_effect = is_software_effect(effect) or is_reactive_effect(effect)

        # Hardware-only effects (perkey, none) need a blocking fade and
        # auxiliary brightness caps so _resolve_brightness stays aligned.
        # Loop effects (reactive, SW) use the render loop's per-frame
        # stability guard for smooth ramping — capping reactive_brightness
        # would make pulses invisible during the ramp window.
        _saved_reactive_br = None
        _saved_perkey_br = None
        if _will_fade and not is_loop_effect:
            _saved_reactive_br = getattr(tray.engine, "reactive_brightness", None)
            tray.engine.reactive_brightness = start_brightness
            _saved_perkey_br = getattr(tray.engine, "per_key_brightness", None)
            if _saved_perkey_br is not None:
                tray.engine.per_key_brightness = start_brightness

        tray.engine.start_effect(
            effect,
            speed=tray.config.get_effect_speed(effect),
            brightness=start_brightness,
            color=tray.config.color,
            reactive_color=getattr(tray.config, "reactive_color", None),
            reactive_use_manual_color=bool(getattr(tray.config, "reactive_use_manual_color", False)),
            direction=getattr(tray.config, "direction", None),
        )
        tray.is_off = False

        # Sync the global speed to the per-effect speed that was just started
        # so the tray speed-menu checkmark shows the correct value for this
        # effect.  Skipping the write when they already match avoids a spurious
        # config-poller restart.
        effective_speed = tray.config.get_effect_speed(effect)
        if effective_speed != safe_int_attr(tray.config, "speed", default=effective_speed):
            tray.config.speed = effective_speed

        if _will_fade:
            if is_loop_effect:
                # The render loop's stability guard ramps brightness
                # frame-by-frame (~8 units/frame).  Just set the target
                # atomically — no blocking fade, no aux caps needed.
                tray.engine.set_brightness(
                    target_brightness,
                    apply_to_hardware=False,
                )
            else:
                tray.engine.set_brightness(
                    target_brightness,
                    apply_to_hardware=True,
                    fade=True,
                    fade_duration_s=float(fade_in_duration_s),
                )
            # Restore auxiliary brightness for hardware effects.
            if _saved_reactive_br is not None:
                try:
                    tray.engine.reactive_brightness = int(_saved_reactive_br)
                except (AttributeError, TypeError, ValueError, OverflowError):
                    pass
            if _saved_perkey_br is not None:
                try:
                    tray.engine.per_key_brightness = int(_saved_perkey_br)
                except (AttributeError, TypeError, ValueError, OverflowError):
                    pass

        if not is_loop_effect and software_effect_target_routes_aux_devices(tray):
            restore_secondary_software_targets(tray)
    except _START_CURRENT_EFFECT_RUNTIME_EXCEPTIONS as exc:  # @quality-exception exception-transparency: lighting startup crosses device I/O, backend callbacks, tray actions; must not fail tray runtime for recoverable failures
        # If the USB device disappeared, mark it unavailable and avoid a scary traceback.
        if is_device_disconnected(exc):
            try:
                tray.engine.mark_device_unavailable()
            except _LOCAL_COMPATIBILITY_FALLBACK_EXCEPTIONS as mark_exc:
                _log_boundary_exception(tray, "Failed to mark device unavailable: %s", mark_exc)
            logger.warning("Keyboard device unavailable: %s", exc)
            return

        # Missing permissions should be surfaced as a user-visible notification.
        if is_permission_denied(exc):
            try:
                tray._notify_permission_issue(exc)
            except _LOCAL_COMPATIBILITY_FALLBACK_EXCEPTIONS as notify_exc:
                _log_boundary_exception(tray, "Failed to notify permission issue: %s", notify_exc)
            return
        _log_boundary_exception(tray, "Error starting effect: %s", exc)


def on_speed_clicked(tray: LightingTrayProtocol, item: object) -> None:
    speed = parse_menu_int(item)
    if speed is None:
        return

    try_log_event(
        tray,
        "menu",
        "set_speed",
        old=safe_int_attr(tray.config, "speed", default=0),
        new=int(speed),
    )

    # Save globally and as a per-effect override so each effect remembers its speed.
    tray.config.speed = speed
    effect = get_effect_name(tray)
    if effect and effect not in {"none", "perkey"}:
        tray.config.set_effect_speed(effect, speed)

    if not tray.is_off:
        is_loop = is_software_effect(effect) or is_reactive_effect(effect)
        if is_loop:
            # SW/reactive loops read engine.speed on every frame — update in-place
            # without restarting the loop (avoids flicker and state loss).
            try:
                tray.engine.speed = speed
            except _LOCAL_COMPATIBILITY_FALLBACK_EXCEPTIONS as exc:
                _log_boundary_exception(tray, "Failed to update engine speed in place: %s", exc)
                start_current_effect(tray)
        else:
            start_current_effect(tray)
    tray._update_menu()


def on_brightness_clicked(tray: LightingTrayProtocol, item: object) -> None:
    brightness = parse_menu_int(item)
    if brightness is None:
        return

    brightness_hw = brightness * 5
    if brightness_hw > 0:
        tray._last_brightness = brightness_hw

    effect = get_effect_name(tray)
    is_sw_effect = is_software_effect(effect)
    is_reactive = is_reactive_effect(effect)

    # Any effect that runs a loop (software or reactive typing) reads
    # `engine.brightness` on each frame. For these, avoid restarting the loop
    # and avoid issuing an extra hardware brightness write (some firmware
    # flashes on separate brightness commands).
    is_loop_effect = bool(is_sw_effect or is_reactive)

    try_log_event(
        tray,
        "menu",
        "set_brightness",
        old=safe_int_attr(tray.config, "brightness", default=0),
        new=int(brightness_hw),
    )

    tray.config.brightness = brightness_hw

    # For reactive typing effects, keep the tray brightness menu behaving like
    # an "overall brightness" control so the user sees an immediate change.
    # The dedicated reactive UI slider can still be used to set a different
    # pulse intensity.
    if is_reactive:
        try:
            tray.config.reactive_brightness = int(brightness_hw)
        except (AttributeError, TypeError, ValueError, OverflowError):
            pass
        try:
            tray.engine.reactive_brightness = int(brightness_hw)
        except (AttributeError, TypeError, ValueError, OverflowError):
            pass

    tray.engine.set_brightness(tray.config.brightness, apply_to_hardware=not is_loop_effect)
    if not tray.is_off and not is_loop_effect:
        start_current_effect(tray)
    tray._update_menu()


def turn_off(tray: LightingTrayProtocol) -> None:
    turn_off_impl(
        tray,
        try_log_event=try_log_event,
        software_effect_target_routes_aux_devices=software_effect_target_routes_aux_devices,
        turn_off_secondary_software_targets=turn_off_secondary_software_targets,
    )


def turn_on(tray: LightingTrayProtocol) -> None:
    turn_on_impl(
        tray,
        try_log_event=try_log_event,
        start_current_effect=start_current_effect,
    )


def power_turn_off(tray: LightingTrayProtocol) -> None:
    power_turn_off_impl(
        tray,
        try_log_event=try_log_event,
        software_effect_target_routes_aux_devices=software_effect_target_routes_aux_devices,
        turn_off_secondary_software_targets=turn_off_secondary_software_targets,
    )


def power_restore(tray: LightingTrayProtocol) -> None:
    power_restore_impl(
        tray,
        try_log_event=try_log_event,
        safe_int_attr_fn=safe_int_attr,
        start_current_effect=start_current_effect,
    )


def apply_brightness_from_power_policy(tray: LightingTrayProtocol, brightness: int) -> None:
    """Best-effort brightness apply used by PowerManager battery-saver."""

    apply_brightness_from_power_policy_impl(
        tray,
        brightness,
        start_current_effect=start_current_effect,
    )
