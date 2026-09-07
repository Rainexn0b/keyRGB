from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Protocol, cast

import keyrgb.core.effects.catalog as effects_catalog
from keyrgb.core.backends.base import normalize_backend_capabilities
from keyrgb.core.secondary_device_routes import route_for_context_entry
from keyrgb.tray.controllers.view_snapshots import secondary_profile_routes_available

from . import (
    _menu_callbacks as menu_callbacks,
    _menu_sections_effects as menu_effects,
    _menu_sections_secondary as menu_secondary,
    menu_sections,
    menu_status,
)

logger = logging.getLogger(__name__)

_MenuAction = Callable[[object, object], None]


class _MenuConfigProtocol(Protocol):
    effect: object
    speed: int
    brightness: int
    software_effect_target: object


class _MenuTrayProtocol(Protocol):
    backend: object | None
    backend_caps: object | None
    config: _MenuConfigProtocol
    is_off: bool

    _on_reactive_color_clicked: _MenuAction
    _on_speed_clicked: _MenuAction
    _on_brightness_clicked: _MenuAction
    _on_hardware_static_mode_clicked: _MenuAction
    _on_hardware_color_clicked: _MenuAction
    _on_selected_device_color_clicked: _MenuAction
    _on_selected_device_brightness_clicked: _MenuAction
    _on_selected_device_turn_off_clicked: _MenuAction
    _on_selected_device_turn_on_clicked: _MenuAction
    _on_power_settings_clicked: _MenuAction
    _on_power_mode_settings_clicked: _MenuAction
    _on_off_clicked: _MenuAction
    _on_turn_on_clicked: _MenuAction
    _on_quit_clicked: _MenuAction

    def _on_effect_key_clicked(self, effect: str) -> None: ...

    def _on_device_context_clicked(self, context_key: str) -> None: ...

    def _on_software_effect_target_clicked(self, target_key: str) -> None: ...


def _menu_tray(tray: object) -> _MenuTrayProtocol:
    return cast(_MenuTrayProtocol, tray)


def normalize_effect_label(label: str) -> str:
    """Normalize a user-visible menu label into a stable effect key.

    Historically, menu labels included decorative glyphs/emojis. We now keep
    labels plain, but still accept older label formats for compatibility.
    """

    s = str(label or "")
    # Remove variation selectors often present in older glyph labels.
    s = s.replace("\ufe0f", "")
    # Drop leading non-word glyphs (bullets, icons, etc).
    s = re.sub(r"^\W+", "", s, flags=re.UNICODE).strip()
    s = s.lower()
    # Convert human label spacing to effect_key style.
    s = re.sub(r"\s+", "_", s)
    return effects_catalog.normalize_effect_name(s)


def build_menu_items(
    tray: object,
    *,
    pystray: menu_sections._PystrayProtocol,
    item: menu_sections._ItemFactoryProtocol,
) -> list[object]:
    """Build menu items list for dynamic menu updates."""

    tray_state = _menu_tray(tray)
    caps = normalize_backend_capabilities(getattr(tray_state, "backend_caps", None))
    per_key_supported = caps.per_key
    hw_effects_supported = caps.hardware_effects
    color_supported = caps.color
    brightness_supported = caps.brightness

    # Determine current mode for lockdown logic
    sw_mode = menu_status.is_software_mode(tray)
    hw_mode = menu_status.is_hardware_mode(tray)
    secondary_lighting_supported = secondary_profile_routes_available(tray)

    all_device_entries = menu_status.device_context_entries(tray)
    if not all_device_entries:
        all_device_entries = [
            {"key": "keyboard", "device_type": "keyboard", "text": menu_status.keyboard_status_text(tray)}
        ]
    selected_key = menu_status.selected_device_context_key(tray, entries=all_device_entries)
    selected_context = next(
        (entry for entry in all_device_entries if str(entry.get("key") or "") == selected_key),
        all_device_entries[0],
    )
    selected_is_keyboard = str(selected_context.get("device_type") or "keyboard").strip().lower() == "keyboard"
    selected_route = None if selected_is_keyboard else route_for_context_entry(selected_context)

    hw_effect_names = effects_catalog.detected_backend_hw_effect_names(getattr(tray_state, "backend", None))
    hw_effects_label = menu_status.hardware_effects_menu_text(tray)

    # HW effects lock when in SW mode; static hardware mode is a separate top-level action.
    hw_effects_menu = menu_effects.build_hw_effects_menu(
        tray_state,
        pystray=pystray,
        item=item,
        hw_mode=hw_mode,
        hw_effect_names=tuple(hw_effect_names),
    )
    sw_effects_menu = menu_effects.build_sw_effects_menu(
        tray_state,
        pystray=pystray,
        item=item,
        sw_mode=sw_mode,
    )
    speed_menu = menu_effects.build_speed_menu(tray_state, pystray=pystray, item=item)
    brightness_menu = menu_effects.build_brightness_menu(tray_state, pystray=pystray, item=item)

    # Lightweight system power mode toggle (cpufreq sysfs). If not available, hide.
    system_power_menu = menu_sections.build_system_power_mode_menu(
        cast(menu_sections._SystemPowerMenuTrayProtocol, tray),
        pystray=pystray,
        item=item,
    )

    perkey_menu = menu_sections.build_perkey_profiles_menu(
        cast(menu_sections._PerkeyMenuTrayProtocol, tray),
        pystray=pystray,
        item=item,
        per_key_supported=per_key_supported,
        secondary_lighting_supported=secondary_lighting_supported,
    )
    power_menu = system_power_menu

    header_items = [
        item(
            str(entry.get("text") or menu_status.keyboard_status_text(tray)),
            menu_callbacks.device_context_callback(tray_state, str(entry.get("key") or "keyboard")),
            checked=menu_callbacks.checked_device_context(selected_context, str(entry.get("key") or "keyboard")),
            radio=True,
        )
        for entry in all_device_entries
    ]

    if selected_is_keyboard:
        selected_brightness_item = (
            item("Brightness Override", brightness_menu)
            if brightness_supported
            else item("Brightness Override (not supported)", None, enabled=False)
        )
        hardware_mode_items: list[object] = [
            item(
                "Hardware Static Mode",
                tray_state._on_hardware_static_mode_clicked,
                checked=menu_callbacks.checked_hw_static(tray_state, hw_mode=hw_mode),
            )
        ]
        if color_supported and hw_mode:
            hardware_mode_items.append(
                item(
                    "Hardware Uniform Color…",
                    tray_state._on_hardware_color_clicked,
                )
            )
        if hw_effects_supported and hw_mode:
            hardware_mode_items.append(
                item(
                    hw_effects_label,
                    hw_effects_menu,
                    enabled=bool(hw_effect_names),
                )
            )
    else:
        controls_available = menu_status.device_context_controls_available(tray, selected_context)
        selected_brightness_item, hardware_mode_items = menu_secondary.build_selected_secondary_section(
            cast(menu_secondary._SecondaryMenuTrayProtocol, tray_state),
            pystray=pystray,
            item=item,
            selected_context=selected_context,
            selected_route=selected_route,
            controls_available=controls_available,
        )

    return [
        *header_items,
        pystray.Menu.SEPARATOR,
        selected_brightness_item,
        *([item("Lighting Profiles", perkey_menu)] if perkey_menu is not None else []),
        pystray.Menu.SEPARATOR,
        *hardware_mode_items,
        pystray.Menu.SEPARATOR,
        item("Software Effects", sw_effects_menu),
        item("Effect Speed", speed_menu),
        pystray.Menu.SEPARATOR,
        # power mode / settings (Support Tools lives under Settings → Version)
        *([item("Power Mode", power_menu)] if power_menu is not None else []),
        item("Settings", tray_state._on_power_settings_clicked),
        pystray.Menu.SEPARATOR,
        # off/on / (active mode) / quit
        item(
            "Turn Off" if not tray_state.is_off else "Turn On",
            tray_state._on_off_clicked if not tray_state.is_off else tray_state._on_turn_on_clicked,
            checked=lambda _i: tray_state.is_off,
        ),
        item(
            menu_status.tray_lighting_mode_text(tray),
            lambda _icon, _item: None,
            enabled=False,
        ),
        item("Quit", tray_state._on_quit_clicked),
    ]


def build_menu(
    tray: object,
    *,
    pystray: menu_sections._PystrayProtocol,
    item: menu_sections._ItemFactoryProtocol,
) -> object:
    """Build a pystray.Menu object."""

    return pystray.Menu(*build_menu_items(tray, pystray=pystray, item=item))
