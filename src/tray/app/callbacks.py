"""Tray menu callback handlers.

These functions contain the operational logic behind tray menu actions.
`KeyRGBTray` keeps the bound-method surface area for pystray, but delegates
into this module to keep the class smaller.
"""

from __future__ import annotations

from typing import Any

import src.core.tcc_power_profiles as tcc_power_profiles

from ..controllers.effect_selection import apply_effect_selection
from ..controllers.lighting_controller import (
    on_brightness_clicked,
    on_speed_clicked,
    turn_off,
    turn_on,
)
from ..ui import menu as menu_mod
from ..ui.gui_launch import (
    launch_perkey_gui,
    launch_power_gui,
    launch_reactive_color_gui,
    launch_tcc_profiles_gui,
    launch_uniform_gui,
)



def on_effect_clicked(tray: Any, item: Any) -> None:
    effect_name = menu_mod.normalize_effect_label(item)
    apply_effect_selection(tray, effect_name=effect_name)

    # Reflect state changes immediately.
    if hasattr(tray, "_refresh_ui"):
        tray._refresh_ui()


def on_effect_key_clicked(tray: Any, effect_name: str) -> None:
    """Apply a specific effect key (already normalized).

    This avoids relying on parsing menu labels and allows menus to show
    user-friendly labels while using stable internal effect identifiers.
    """

    apply_effect_selection(tray, effect_name=str(effect_name or "none").strip().lower())
    if hasattr(tray, "_refresh_ui"):
        tray._refresh_ui()


def on_speed_clicked_cb(tray: Any, item: Any) -> None:
    on_speed_clicked(tray, item)


def on_brightness_clicked_cb(tray: Any, item: Any) -> None:
    on_brightness_clicked(tray, item)


def on_off_clicked(tray: Any) -> None:
    turn_off(tray)


def on_turn_on_clicked(tray: Any) -> None:
    turn_on(tray)


def on_perkey_clicked() -> None:
    launch_perkey_gui()


def on_uniform_gui_clicked() -> None:
    launch_uniform_gui()


def on_reactive_color_gui_clicked() -> None:
    launch_reactive_color_gui()


def on_hardware_color_clicked(tray: Any) -> None:
    """Switch to hardware uniform mode, then open the uniform color GUI."""

    apply_effect_selection(tray, effect_name="hw_uniform")
    if hasattr(tray, "_refresh_ui"):
        tray._refresh_ui()

    launch_uniform_gui()


def on_power_settings_clicked() -> None:
    launch_power_gui()


def on_tcc_profiles_gui_clicked() -> None:
    launch_tcc_profiles_gui()


def on_tcc_profile_clicked(tray: Any, profile_id: str) -> None:
    """Switch TUXEDO Control Center power profile (temporary) via DBus."""

    try:
        tcc_power_profiles.set_temp_profile_by_id(profile_id)
    finally:
        # Reflect updated active profile state.
        if hasattr(tray, "_update_menu"):
            tray._update_menu()
