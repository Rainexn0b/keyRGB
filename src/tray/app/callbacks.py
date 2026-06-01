"""Tray menu callback handlers.

These functions contain the operational logic behind tray menu actions.
`KeyRGBTray` keeps the bound-method surface area for pystray, but delegates
into this module to keep the class smaller.
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Mapping

from src.core.effects.catalog import is_backend_hardware_effect, normalize_effect_name
from src.tray.protocols import LightingTrayProtocol, ensure_tray_idle_power_state

from ..controllers import effect_selection, lighting_controller, secondary_device_controller, software_target_controller
from ..ui import menu as menu_mod
from ..ui import gui_launch
from ..ui.menu_status import is_hardware_mode, selected_device_context_entry

apply_effect_selection = effect_selection.apply_effect_selection
on_brightness_clicked = lighting_controller.on_brightness_clicked
on_speed_clicked = lighting_controller.on_speed_clicked
turn_off = lighting_controller.turn_off
turn_on = lighting_controller.turn_on
apply_selected_secondary_brightness = secondary_device_controller.apply_selected_secondary_brightness
selected_secondary_backend_name = secondary_device_controller.selected_secondary_backend_name
turn_on_selected_secondary_device = secondary_device_controller.turn_on_selected_secondary_device
turn_off_selected_secondary_device = secondary_device_controller.turn_off_selected_secondary_device
apply_software_effect_target_selection = software_target_controller.apply_software_effect_target_selection
launch_perkey_gui = gui_launch.launch_perkey_gui
launch_power_gui = gui_launch.launch_power_gui
launch_power_mode_settings_gui = gui_launch.launch_power_mode_settings_gui
launch_reactive_color_gui = gui_launch.launch_reactive_color_gui
launch_support_gui = gui_launch.launch_support_gui
launch_uniform_gui = gui_launch.launch_uniform_gui
_RECOVERABLE_UI_CALLBACK_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _run_ui_callback_best_effort(action: Callable[[], None]) -> None:
    try:
        action()
    except _RECOVERABLE_UI_CALLBACK_ERRORS:  # @quality-exception exception-transparency: tray refresh/menu callbacks share a best-effort runtime boundary so recoverable UI failures stay non-fatal while unexpected bugs still propagate
        pass


def _refresh_ui_best_effort(tray: LightingTrayProtocol) -> None:
    _run_ui_callback_best_effort(lambda: tray._refresh_ui())


def _update_menu_best_effort(tray: LightingTrayProtocol) -> None:
    _run_ui_callback_best_effort(lambda: tray._update_menu())


def _is_hardware_static_mode_active(tray: LightingTrayProtocol) -> bool:
    config = getattr(tray, "config", None)
    effect = str(getattr(config, "effect", "none") or "none").strip().lower()
    return is_hardware_mode(tray) and effect == "none" and not bool(getattr(tray, "is_off", False))


def _track_hardware_toggle_transition_state(tray: LightingTrayProtocol, *, effect_name: str) -> None:
    normalized = normalize_effect_name(str(effect_name or "none").strip().lower())
    entering_hardware = normalized in {"hw_uniform", "hardware_uniform"} or is_backend_hardware_effect(
        normalized, getattr(tray, "backend", None)
    )
    state = ensure_tray_idle_power_state(tray)

    if entering_hardware and not is_hardware_mode(tray):
        _snapshot_hardware_toggle_software_state(tray)

    if entering_hardware:
        state.hardware_toggle_restore_hardware_effect = (
            "none" if normalized in {"hw_uniform", "hardware_uniform"} else normalized
        )
        state.hardware_toggle_restore_hardware_color = getattr(getattr(tray, "config", None), "color", None)
        return

    if is_hardware_mode(tray):
        _snapshot_hardware_toggle_hardware_state(tray)


def on_effect_clicked(tray: LightingTrayProtocol, item: object) -> None:
    effect_name = menu_mod.normalize_effect_label(str(item))
    _track_hardware_toggle_transition_state(tray, effect_name=effect_name)
    apply_effect_selection(tray, effect_name=effect_name)

    # Reflect state changes immediately.
    _refresh_ui_best_effort(tray)


def on_effect_key_clicked(tray: LightingTrayProtocol, effect_name: str) -> None:
    """Apply a specific effect key (already normalized).

    This avoids relying on parsing menu labels and allows menus to show
    user-friendly labels while using stable internal effect identifiers.
    """
    normalized = str(effect_name or "none").strip().lower()
    _track_hardware_toggle_transition_state(tray, effect_name=normalized)
    apply_effect_selection(tray, effect_name=normalized)
    _refresh_ui_best_effort(tray)


def on_speed_clicked_cb(tray: LightingTrayProtocol, item: object) -> None:
    on_speed_clicked(tray, item)


def on_brightness_clicked_cb(tray: LightingTrayProtocol, item: object) -> None:
    on_brightness_clicked(tray, item)


def on_device_context_clicked(tray: LightingTrayProtocol, context_key: str) -> None:
    normalized = str(context_key or "keyboard") or "keyboard"
    try:
        tray.selected_device_context = normalized
    except AttributeError:
        return

    try:
        tray.config.tray_device_context = normalized
    except AttributeError:
        pass

    _update_menu_best_effort(tray)


def on_software_effect_target_clicked(tray: LightingTrayProtocol, target_key: str) -> None:
    apply_software_effect_target_selection(tray, target_key)
    _update_menu_best_effort(tray)


def on_off_clicked(tray: LightingTrayProtocol) -> None:
    turn_off(tray)


def on_turn_on_clicked(tray: LightingTrayProtocol) -> None:
    turn_on(tray)


def on_perkey_clicked() -> None:
    launch_perkey_gui()


def on_uniform_gui_clicked() -> None:
    launch_uniform_gui()


def on_reactive_color_gui_clicked() -> None:
    launch_reactive_color_gui()


def _snapshot_hardware_toggle_software_state(tray: LightingTrayProtocol) -> None:
    state = ensure_tray_idle_power_state(tray)
    config = getattr(tray, "config", None)
    effect = str(getattr(config, "effect", "none") or "none").strip().lower()
    per_key_colors = getattr(config, "per_key_colors", None)
    per_key_snapshot = dict(per_key_colors) if isinstance(per_key_colors, Mapping) else {}
    software_target = str(getattr(config, "software_effect_target", "keyboard") or "keyboard")

    state.hardware_toggle_restore_effect = effect
    state.hardware_toggle_restore_per_key_colors = per_key_snapshot
    state.hardware_toggle_restore_software_target = software_target


def _snapshot_hardware_toggle_hardware_state(tray: LightingTrayProtocol) -> None:
    state = ensure_tray_idle_power_state(tray)
    config = getattr(tray, "config", None)
    effect = str(getattr(config, "effect", "none") or "none").strip().lower()
    color = getattr(config, "color", None)

    state.hardware_toggle_restore_hardware_effect = effect
    state.hardware_toggle_restore_hardware_color = color


def _restore_hardware_toggle_software_state(tray: LightingTrayProtocol) -> str:
    state = ensure_tray_idle_power_state(tray)
    config = getattr(tray, "config", None)
    restore_effect = str(state.hardware_toggle_restore_effect or "none").strip().lower()
    restore_per_key_colors = state.hardware_toggle_restore_per_key_colors or {}
    restore_software_target = str(state.hardware_toggle_restore_software_target or "keyboard").strip().lower()

    if config is not None:
        try:
            config.per_key_colors = dict(restore_per_key_colors) if isinstance(restore_per_key_colors, Mapping) else {}
        except (AttributeError, TypeError, ValueError):
            pass

        try:
            config.software_effect_target = restore_software_target
        except (AttributeError, TypeError, ValueError):
            pass

    return restore_effect


def _restore_hardware_toggle_hardware_effect(tray: LightingTrayProtocol) -> str:
    state = ensure_tray_idle_power_state(tray)
    config = getattr(tray, "config", None)
    raw_restore_effect = state.hardware_toggle_restore_hardware_effect
    restore_effect = str(raw_restore_effect).strip().lower() if isinstance(raw_restore_effect, str) else "none"
    restore_color = state.hardware_toggle_restore_hardware_color

    if config is not None:
        try:
            if restore_color is not None:
                config.color = restore_color
        except (AttributeError, TypeError, ValueError):
            pass

    if restore_effect in {"", "none", "hw_uniform", "hardware_uniform"}:
        return "hw_uniform"
    return restore_effect


def on_hardware_static_mode_clicked(tray: LightingTrayProtocol) -> None:
    """Toggle hardware static mode on/off from the tray."""

    if _is_hardware_static_mode_active(tray):
        _snapshot_hardware_toggle_hardware_state(tray)
        restore_effect = _restore_hardware_toggle_software_state(tray)
        apply_effect_selection(tray, effect_name=restore_effect)
        _refresh_ui_best_effort(tray)
        return

    if is_hardware_mode(tray):
        _snapshot_hardware_toggle_hardware_state(tray)
        apply_effect_selection(tray, effect_name="hw_uniform")
        _refresh_ui_best_effort(tray)
        return

    _snapshot_hardware_toggle_software_state(tray)
    restore_hardware_effect = _restore_hardware_toggle_hardware_effect(tray)
    apply_effect_selection(tray, effect_name=restore_hardware_effect)
    _refresh_ui_best_effort(tray)


def on_hardware_color_clicked(tray: LightingTrayProtocol) -> None:
    """Switch to hardware static mode, then open the uniform color GUI."""

    on_hardware_static_mode_clicked(tray)

    launch_uniform_gui()


def on_selected_device_color_clicked(tray: LightingTrayProtocol) -> None:
    entry = selected_device_context_entry(tray)
    device_type = str(entry.get("device_type") or "keyboard").strip().lower()
    if device_type == "keyboard":
        on_hardware_color_clicked(tray)
        return

    backend_name = selected_secondary_backend_name(tray)
    launch_uniform_gui(target_context=str(entry.get("key") or device_type), backend_name=backend_name)


def on_selected_device_brightness_clicked(tray: LightingTrayProtocol, item: object) -> None:
    entry = selected_device_context_entry(tray)
    device_type = str(entry.get("device_type") or "keyboard").strip().lower()
    if device_type == "keyboard":
        on_brightness_clicked(tray, item)
        return
    apply_selected_secondary_brightness(tray, item)


def on_selected_device_turn_off_clicked(tray: LightingTrayProtocol) -> None:
    entry = selected_device_context_entry(tray)
    device_type = str(entry.get("device_type") or "keyboard").strip().lower()
    if device_type == "keyboard":
        turn_off(tray)
        return
    turn_off_selected_secondary_device(tray)


def on_selected_device_turn_on_clicked(tray: LightingTrayProtocol) -> None:
    entry = selected_device_context_entry(tray)
    device_type = str(entry.get("device_type") or "keyboard").strip().lower()
    if device_type == "keyboard":
        turn_on(tray)
        return
    turn_on_selected_secondary_device(tray)


def on_power_settings_clicked() -> None:
    launch_power_gui()


def on_power_mode_settings_clicked() -> None:
    launch_power_mode_settings_gui()


def on_support_debug_clicked() -> None:
    launch_support_gui(focus="debug")


def on_backend_discovery_clicked() -> None:
    launch_support_gui(focus="discovery")
