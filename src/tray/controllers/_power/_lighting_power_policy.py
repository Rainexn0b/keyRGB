from __future__ import annotations

from collections.abc import Callable

from src.tray.idle_power_state import is_system_forced_off, is_user_forced_off
from src.tray.protocols import LightingTrayProtocol

from src.tray.controllers._brightness_layer import apply_layered_brightness_update
from src.tray.controllers._lighting_controller_helpers import _log_tray_exception


_BRIGHTNESS_COERCION_EXCEPTIONS = (TypeError, ValueError, OverflowError)
# Power-policy brightness apply (config/engine/UI); LookupError kept for tested UI callback failures.
_POWER_POLICY_RUNTIME_EXCEPTIONS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def apply_brightness_from_power_policy_impl(
    tray: LightingTrayProtocol,
    brightness: int,
    *,
    start_current_effect: Callable[[LightingTrayProtocol], None],
) -> None:
    try:
        brightness_int = int(brightness)
    except _BRIGHTNESS_COERCION_EXCEPTIONS:
        return

    if brightness_int < 0:
        return

    if is_user_forced_off(tray):
        return

    if is_system_forced_off(tray):
        return

    try:
        apply_layered_brightness_update(
            tray,
            source="power_policy",
            base_brightness=brightness_int,
            reactive_brightness=None,
            reactive_source_label="power policy",
            start_current_effect=start_current_effect,
        )
    except _POWER_POLICY_RUNTIME_EXCEPTIONS as exc:  # @quality-exception exception-transparency: power-policy application crosses config setters, backend runtime calls, and UI callbacks; must remain non-fatal
        _log_tray_exception(tray, "Failed to apply tray lighting power-policy brightness: %s", exc)
        return
