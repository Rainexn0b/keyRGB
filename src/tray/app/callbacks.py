"""Tray menu callback handlers.

These functions contain the operational logic behind tray menu actions.
`KeyRGBTray` keeps the bound-method surface area for pystray, but delegates
into this module to keep the class smaller.
"""

from __future__ import annotations

from src.tray.protocols import LightingTrayProtocol

import src.core.power.tcc_profiles as tcc_power_profiles

from ..controllers import effect_selection, lighting_controller, secondary_device_controller, software_target_controller
from ..ui import menu as menu_mod
from ..ui import gui_launch
from ..ui.menu_status import selected_device_context_entry

apply_effect_selection = effect_selection.apply_effect_selection
on_brightness_clicked = lighting_controller.on_brightness_clicked
on_speed_clicked = lighting_controller.on_speed_clicked
turn_off = lighting_controller.turn_off
turn_on = lighting_controller.turn_on
apply_selected_secondary_brightness = secondary_device_controller.apply_selected_secondary_brightness
selected_secondary_backend_name = secondary_device_controller.selected_secondary_backend_name
turn_off_selected_secondary_device = secondary_device_controller.turn_off_selected_secondary_device
apply_software_effect_target_selection = software_target_controller.apply_software_effect_target_selection
launch_perkey_gui = gui_launch.launch_perkey_gui
launch_power_gui = gui_launch.launch_power_gui
launch_reactive_color_gui = gui_launch.launch_reactive_color_gui
launch_support_gui = gui_launch.launch_support_gui
launch_tcc_profiles_gui = gui_launch.launch_tcc_profiles_gui
launch_uniform_gui = gui_launch.launch_uniform_gui
_RECOVERABLE_UI_CALLBACK_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)


def _refresh_ui_best_effort(tray: LightingTrayProtocol) -> None:
    try:
        tray._refresh_ui()
    except (
        _RECOVERABLE_UI_CALLBACK_ERRORS
    ):  # @quality-exception exception-transparency: tray UI refresh is a best-effort runtime boundary
        pass


def _update_menu_best_effort(tray: LightingTrayProtocol) -> None:
    try:
        tray._update_menu()
    except (
        _RECOVERABLE_UI_CALLBACK_ERRORS
    ):  # @quality-exception exception-transparency: tray menu rebuild is a best-effort runtime boundary
        pass


def on_effect_clicked(tray: LightingTrayProtocol, item: object) -> None:
    effect_name = menu_mod.normalize_effect_label(str(item))
    apply_effect_selection(tray, effect_name=effect_name)

    # Reflect state changes immediately.
    _refresh_ui_best_effort(tray)


def on_effect_key_clicked(tray: LightingTrayProtocol, effect_name: str) -> None:
    """Apply a specific effect key (already normalized).

    This avoids relying on parsing menu labels and allows menus to show
    user-friendly labels while using stable internal effect identifiers.
    """

    apply_effect_selection(tray, effect_name=str(effect_name or "none").strip().lower())
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


def on_hardware_static_mode_clicked(tray: LightingTrayProtocol) -> None:
    """Switch to hardware static mode without opening the color picker."""

    apply_effect_selection(tray, effect_name="hw_uniform")
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


def on_power_settings_clicked() -> None:
    launch_power_gui()


def on_support_debug_clicked() -> None:
    launch_support_gui(focus="debug")


def on_backend_discovery_clicked() -> None:
    launch_support_gui(focus="discovery")


def on_tcc_profiles_gui_clicked() -> None:
    launch_tcc_profiles_gui()


def on_tcc_profile_clicked(tray: LightingTrayProtocol, profile_id: str) -> None:
    """Switch TUXEDO Control Center power profile (temporary) via DBus."""

    try:
        tcc_power_profiles.set_temp_profile_by_id(profile_id)
    finally:
        # Reflect updated active profile state.
        _update_menu_best_effort(tray)
