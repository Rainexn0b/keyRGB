from __future__ import annotations

import logging
from typing import Optional

from src.core.effects import catalog as effects_catalog
from src.core.utils import exceptions as core_exceptions
from src.core.utils import safe_attrs
from src.tray.controllers import _lighting_controller_helpers as lighting_controller_helpers
from src.tray.controllers import _lighting_effect_coordination as lighting_effect_coordination
from src.tray.controllers import _lighting_menu_handlers as lighting_menu_handlers
from src.tray.controllers import _lighting_start_effect_boundary as lighting_start_effect_boundary
from src.tray.controllers import software_target_controller
from src.tray.controllers._power import _lighting_power_policy as lighting_power_policy
from src.tray.controllers._power import _lighting_power_state as lighting_power_state
from src.tray.protocols import LightingTrayProtocol


SW_EFFECTS = effects_catalog.SW_EFFECTS_SET
restore_secondary_software_targets = software_target_controller.restore_secondary_software_targets

logger = logging.getLogger(__name__)


_START_CURRENT_EFFECT_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)
_TRAY_LOGGER_CALLBACK_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _log_boundary_exception(tray: LightingTrayProtocol, msg: str, exc: Exception) -> None:
    """Log an exception via the tray with fallback error logging."""

    def _recover_tray_logging(log_exc: Exception) -> None:
        logger.exception("Tray exception logger failed while logging boundary: %s", log_exc)
        logger.error(msg, exc, exc_info=(type(exc), exc, exc.__traceback__))

    lighting_controller_helpers._run_diagnostic_boundary(
        lambda: tray._log_exception(msg, exc),
        runtime_exceptions=_TRAY_LOGGER_CALLBACK_EXCEPTIONS,
        on_recoverable=_recover_tray_logging,
    )


def _coerce_brightness_override(brightness_override: object, *, default: int) -> int:
    """Coerce brightness override to valid range [0, 50]; return default on error."""
    return lighting_effect_coordination._coerce_brightness_override(brightness_override, default=default)


def _classify_start_current_effect(
    tray: LightingTrayProtocol,
    *,
    effect: str,
) -> lighting_effect_coordination._StartCurrentEffectPlan:
    """Classify the effect being started (backward-compatible test interface)."""
    return lighting_effect_coordination._classify_start_current_effect(
        tray,
        effect=effect,
        is_software_effect_fn=lighting_controller_helpers.is_software_effect,
        is_reactive_effect_fn=lighting_controller_helpers.is_reactive_effect,
        software_effect_target_routes_aux_devices_fn=software_target_controller.software_effect_target_routes_aux_devices,
    )


def _plan_effect_fade_ramp(
    *,
    effect: str,
    fade_in: bool,
    start_brightness: int,
    target_brightness: int,
) -> lighting_effect_coordination._FadeRampPlan:
    """Plan effect fade ramp strategy (backward-compatible test interface)."""
    return lighting_effect_coordination._plan_effect_fade_ramp(
        effect=effect,
        fade_in=fade_in,
        start_brightness=start_brightness,
        target_brightness=target_brightness,
        is_software_effect_fn=lighting_controller_helpers.is_software_effect,
        is_reactive_effect_fn=lighting_controller_helpers.is_reactive_effect,
    )


def _resolve_start_current_effect_policy(
    tray: LightingTrayProtocol,
    *,
    brightness_override: Optional[int],
) -> lighting_effect_coordination._StartCurrentEffectPolicy:
    """Resolve start_current_effect policy before invoking engine side effects."""
    return lighting_effect_coordination._resolve_start_current_effect_policy(
        tray,
        brightness_override=brightness_override,
        safe_int_attr_fn=safe_attrs.safe_int_attr,
        safe_str_attr_fn=safe_attrs.safe_str_attr,
        resolve_effect_name_for_backend_fn=effects_catalog.resolve_effect_name_for_backend,
        coerce_brightness_override_fn=lambda value: _coerce_brightness_override(
            value,
            default=safe_attrs.safe_int_attr(tray.config, "brightness", default=0),
        ),
        classify_start_current_effect_fn=lambda target_tray, effect: _classify_start_current_effect(
            target_tray,
            effect=effect,
        ),
    )


def _run_static_effect_mode(
    tray: LightingTrayProtocol,
    *,
    apply_mode,
    start_brightness: int,
    target_brightness: int,
    fade_in: bool,
    fade_in_duration_s: float,
    restore_secondary_targets: bool,
) -> None:
    """Run a static effect mode (convenience wrapper)."""
    return lighting_effect_coordination._run_static_effect_mode(
        tray,
        apply_mode=apply_mode,
        start_brightness=start_brightness,
        target_brightness=target_brightness,
        fade_in=fade_in,
        fade_in_duration_s=fade_in_duration_s,
        restore_secondary_targets=restore_secondary_targets,
        restore_secondary_software_targets_fn=restore_secondary_software_targets,
    )


def _apply_effect_fade_ramp(
    tray: LightingTrayProtocol,
    *,
    plan: lighting_effect_coordination._FadeRampPlan,
    start_brightness: int,
    target_brightness: int,
    fade_in_duration_s: float,
) -> None:
    """Apply effect fade ramp (convenience wrapper)."""
    return lighting_effect_coordination._apply_effect_fade_ramp(
        tray,
        plan=plan,
        start_brightness=start_brightness,
        target_brightness=target_brightness,
        fade_in_duration_s=fade_in_duration_s,
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
        lighting_controller_helpers.ensure_device_best_effort(tray)

        policy = _resolve_start_current_effect_policy(tray, brightness_override=brightness_override)
        effect = policy.effect
        start_plan = policy.start_plan
        target_brightness = policy.target_brightness
        start_brightness = policy.start_brightness

        if policy.persist_effect is not None:
            tray.config.effect = policy.persist_effect

        if start_plan.is_perkey_mode:
            _run_static_effect_mode(
                tray,
                apply_mode=lighting_controller_helpers.apply_perkey_mode,
                start_brightness=start_brightness,
                target_brightness=target_brightness,
                fade_in=fade_in,
                fade_in_duration_s=fade_in_duration_s,
                restore_secondary_targets=start_plan.restore_secondary_targets,
            )
            return

        if start_plan.is_none_mode:
            _run_static_effect_mode(
                tray,
                apply_mode=lighting_controller_helpers.apply_uniform_none_mode,
                start_brightness=start_brightness,
                target_brightness=target_brightness,
                fade_in=fade_in,
                fade_in_duration_s=fade_in_duration_s,
                restore_secondary_targets=start_plan.restore_secondary_targets,
            )
            return

        # Prepare per-key state in case the effect is a software effect that needs it.
        # This handles cases like 'reactive_ripple' running on startup where the menu logic hasn't run.
        lighting_effect_coordination.prepare_effect_engine_state(
            tray,
            effect=effect,
            is_software_effect_fn=lighting_controller_helpers.is_software_effect,
            set_engine_perkey_from_config_fn=lighting_controller_helpers.set_engine_perkey_from_config_for_sw_effect,
            clear_engine_perkey_state_fn=lighting_controller_helpers.clear_engine_perkey_state,
        )

        # Decide ramp strategy separately from I/O side effects.
        fade_plan = _plan_effect_fade_ramp(
            effect=effect,
            fade_in=fade_in,
            start_brightness=start_brightness,
            target_brightness=target_brightness,
        )

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
        if effective_speed != safe_attrs.safe_int_attr(tray.config, "speed", default=effective_speed):
            tray.config.speed = effective_speed

        _apply_effect_fade_ramp(
            tray,
            plan=fade_plan,
            start_brightness=start_brightness,
            target_brightness=target_brightness,
            fade_in_duration_s=fade_in_duration_s,
        )

        if not start_plan.is_loop_effect and start_plan.restore_secondary_targets:
            restore_secondary_software_targets(tray)
    except _START_CURRENT_EFFECT_RUNTIME_EXCEPTIONS as exc:  # @quality-exception exception-transparency: lighting startup crosses device I/O, backend callbacks, tray actions; must not fail tray runtime for recoverable failures
        lighting_start_effect_boundary.handle_start_current_effect_exception(
            tray,
            exc,
            is_device_disconnected_fn=core_exceptions.is_device_disconnected,
            is_permission_denied_fn=core_exceptions.is_permission_denied,
            log_boundary_exception_fn=_log_boundary_exception,
        )


def on_speed_clicked(tray: LightingTrayProtocol, item: object) -> None:
    lighting_menu_handlers.on_speed_clicked_impl(
        tray,
        item,
        start_current_effect=start_current_effect,
        log_boundary_exception=_log_boundary_exception,
    )


def on_brightness_clicked(tray: LightingTrayProtocol, item: object) -> None:
    lighting_menu_handlers.on_brightness_clicked_impl(
        tray,
        item,
        start_current_effect=start_current_effect,
    )


def turn_off(tray: LightingTrayProtocol) -> None:
    lighting_power_state.turn_off_impl(
        tray,
        try_log_event=lighting_controller_helpers.try_log_event,
        software_effect_target_routes_aux_devices=software_target_controller.software_effect_target_routes_aux_devices,
        turn_off_secondary_software_targets=software_target_controller.turn_off_secondary_software_targets,
    )


def turn_on(tray: LightingTrayProtocol) -> None:
    lighting_power_state.turn_on_impl(
        tray,
        try_log_event=lighting_controller_helpers.try_log_event,
        start_current_effect=start_current_effect,
    )


def power_turn_off(tray: LightingTrayProtocol) -> None:
    lighting_power_state.power_turn_off_impl(
        tray,
        try_log_event=lighting_controller_helpers.try_log_event,
        software_effect_target_routes_aux_devices=software_target_controller.software_effect_target_routes_aux_devices,
        turn_off_secondary_software_targets=software_target_controller.turn_off_secondary_software_targets,
    )


def power_restore(tray: LightingTrayProtocol) -> None:
    lighting_power_state.power_restore_impl(
        tray,
        try_log_event=lighting_controller_helpers.try_log_event,
        safe_int_attr_fn=safe_attrs.safe_int_attr,
        safe_str_attr_fn=safe_attrs.safe_str_attr,
        is_software_effect_fn=lighting_controller_helpers.is_software_effect,
        is_reactive_effect_fn=lighting_controller_helpers.is_reactive_effect,
        start_current_effect=start_current_effect,
    )


def apply_brightness_from_power_policy(tray: LightingTrayProtocol, brightness: int) -> None:
    """Best-effort brightness apply used by PowerManager battery-saver."""

    lighting_power_policy.apply_brightness_from_power_policy_impl(
        tray,
        brightness,
        start_current_effect=start_current_effect,
    )
