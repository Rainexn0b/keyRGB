from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Protocol, cast

import src.core.effects.catalog as effects_catalog
from src.core import secondary_lighting_state
from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE
from src.core.secondary_device_routes import (
    BRIGHTNESS_POLICY_INDEPENDENT,
    BRIGHTNESS_POLICY_PRIMARY_SHARED,
    SecondaryDeviceRoute,
)
from src.core.secondary_device_runtime import has_available_secondary_profile_routes
from src.tray import secondary_device_power
from src.tray.secondary_device_routes import route_for_context_entry

from ..controllers import software_target_controller
from . import _menu_callbacks as menu_callbacks
from . import menu_sections, menu_status


logger = logging.getLogger(__name__)

_MenuAction = Callable[[object, object], None]


class _MenuConfigProtocol(Protocol):
    effect: object
    speed: int
    brightness: int
    software_effect_target: object


class _ReloadableMenuConfigProtocol(_MenuConfigProtocol, Protocol):
    def reload(self) -> None: ...


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
    _on_support_debug_clicked: _MenuAction
    _on_power_settings_clicked: _MenuAction
    _on_power_mode_settings_clicked: _MenuAction
    _on_off_clicked: _MenuAction
    _on_turn_on_clicked: _MenuAction
    _on_quit_clicked: _MenuAction

    def _on_effect_key_clicked(self, effect: str) -> None: ...

    def _on_device_context_clicked(self, context_key: str) -> None: ...

    def _on_software_effect_target_clicked(self, target_key: str) -> None: ...


class _ReloadableMenuTrayProtocol(Protocol):
    config: _ReloadableMenuConfigProtocol


def _menu_tray(tray: object) -> _MenuTrayProtocol:
    return cast(_MenuTrayProtocol, tray)


def _reloadable_menu_tray(tray: object) -> _ReloadableMenuTrayProtocol:
    return cast(_ReloadableMenuTrayProtocol, tray)


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


def _selected_secondary_is_off(tray: object, route: SecondaryDeviceRoute | None) -> bool:
    payload = vars(tray).get("_active_secondary_lighting")
    entry = secondary_lighting_state.area_entry(payload, getattr(route, "state_key", ""))
    if entry is not None and "enabled" in entry:
        return not secondary_lighting_state.entry_enabled(entry)
    return secondary_device_power.is_off(getattr(tray, "config", None), route)


def build_menu_items(
    tray: object,
    *,
    pystray: menu_sections._PystrayProtocol,
    item: menu_sections._ItemFactoryProtocol,
) -> list[object]:
    """Build menu items list for dynamic menu updates."""

    tray_state = _menu_tray(tray)
    caps = getattr(tray_state, "backend_caps", None)
    per_key_supported = bool(getattr(caps, "per_key", True)) if caps is not None else True
    hw_effects_supported = bool(getattr(caps, "hardware_effects", True)) if caps is not None else True
    color_supported = bool(getattr(caps, "color", True)) if caps is not None else True

    menu_status.probe_device_available(tray)

    # Determine current mode for lockdown logic
    sw_mode = menu_status.is_software_mode(tray)
    hw_mode = menu_status.is_hardware_mode(tray)
    secondary_lighting_supported = has_available_secondary_profile_routes()
    secondary_effect_target_supported = software_target_controller.software_effect_target_has_compatible_devices(tray)

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

    # HW effects menu - animated effects lock when in SW mode.
    # Switching back to static hardware mode is now a separate top-level action.
    hw_effects_menu = pystray.Menu(
        *[
            item(
                effects_catalog.title_for_effect(effect),
                menu_callbacks.effect_key_callback(tray_state, effects_catalog.hardware_effect_selection_key(effect)),
                checked=menu_callbacks.checked_hw_effect(
                    tray_state,
                    effects_catalog.hardware_effect_selection_key(effect),
                    hw_mode=hw_mode,
                ),
                radio=True,
                enabled=hw_mode,  # Grey out animated effects when in SW mode
            )
            for effect in hw_effect_names
        ],
    )

    # SW effects work best with per-key colors loaded
    # "None" here means static per-key display, other SW effects locked when in HW mode
    sw_items = [
        item(
            "Reactive Typing Settings…",
            tray_state._on_reactive_color_clicked,
        ),
        pystray.Menu.SEPARATOR,
        item(
            "None (static per-key)",
            menu_callbacks.effect_key_callback(tray_state, "perkey"),
            checked=menu_callbacks.checked_perkey(tray_state),
            radio=True,
        ),
        pystray.Menu.SEPARATOR,
        *[
            item(
                effects_catalog.title_for_effect(effect),
                menu_callbacks.effect_key_callback(tray_state, effect),
                checked=menu_callbacks.checked_sw_effect(tray_state, effect, sw_mode=sw_mode),
                radio=True,
                enabled=sw_mode,
            )
            for effect in effects_catalog.SOFTWARE_EFFECTS
        ],
        pystray.Menu.SEPARATOR,
        *[
            item(
                effects_catalog.title_for_effect(effect),
                menu_callbacks.effect_key_callback(tray_state, effect),
                checked=menu_callbacks.checked_sw_effect(tray_state, effect, sw_mode=sw_mode),
                radio=True,
                enabled=sw_mode,
            )
            for effect in effects_catalog.REACTIVE_EFFECTS
        ],
    ]

    if secondary_effect_target_supported:
        sw_items.extend(
            [
                pystray.Menu.SEPARATOR,
                item(
                    "Include enabled lighting areas",
                    menu_callbacks.toggle_enabled_lighting_areas_callback(tray_state),
                    checked=menu_callbacks.checked_software_target(
                        tray_state,
                        SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE,
                    ),
                ),
            ]
        )

    sw_effects_menu = pystray.Menu(*sw_items)

    speed_menu = pystray.Menu(
        *[
            item(
                str(speed),
                tray_state._on_speed_clicked,
                checked=menu_callbacks.checked_speed(tray_state, speed),
                radio=True,
            )
            for speed in range(0, 11)
        ]
    )

    brightness_menu = pystray.Menu(
        *[
            item(
                str(brightness),
                tray_state._on_brightness_clicked,
                checked=menu_callbacks.checked_brightness(tray_state, brightness * 5),
                radio=True,
            )
            for brightness in range(0, 11)
        ]
    )

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
        selected_brightness_item = item("Brightness Override", brightness_menu)
        hardware_mode_items: list[object] = [
            item(
                "Static Mode",
                tray_state._on_hardware_static_mode_clicked,
                checked=menu_callbacks.checked_hw_static(tray_state, hw_mode=hw_mode),
            )
        ]
        if color_supported:
            hardware_mode_items.append(
                item(
                    "Uniform Color…",
                    tray_state._on_hardware_color_clicked,
                    enabled=hw_mode,
                )
            )
        if hw_effects_supported:
            hardware_mode_items.append(
                item(
                    hw_effects_label,
                    hw_effects_menu,
                    enabled=bool(hw_effect_names) and hw_mode,
                )
            )
    else:
        controls_available = menu_status.device_context_controls_available(tray, selected_context)
        if selected_route is not None and selected_route.brightness_policy == BRIGHTNESS_POLICY_INDEPENDENT:
            selected_brightness_menu = pystray.Menu(
                *[
                    item(
                        str(level),
                        tray_state._on_selected_device_brightness_clicked,
                        checked=lambda _i, current=level, route=selected_route: (
                            secondary_device_power.current_brightness(tray_state.config, route) == current * 5
                        ),
                        radio=True,
                        enabled=controls_available,
                    )
                    for level in range(0, 11)
                ]
            )
            selected_brightness_item = item("Brightness Override", selected_brightness_menu)
        elif selected_route is not None and selected_route.brightness_policy == BRIGHTNESS_POLICY_PRIMARY_SHARED:
            selected_brightness_item = item("Brightness Override (follows Keyboard)", None, enabled=False)
        else:
            selected_brightness_item = item("Brightness Override (not supported)", None, enabled=False)

        device_label = (
            str(getattr(selected_route, "display_name", "") or "").strip()
            or str(selected_context.get("device_type") or "device").replace("_", " ").title()
        )
        selected_device_is_off = _selected_secondary_is_off(tray, selected_route)
        hardware_mode_items = [
            item(
                "Static Color…",
                tray_state._on_selected_device_color_clicked,
                enabled=bool(selected_route and selected_route.supports_uniform_color and controls_available),
            ),
            item(
                f"Turn {'On' if selected_device_is_off else 'Off'} {device_label}",
                (
                    tray_state._on_selected_device_turn_on_clicked
                    if selected_device_is_off
                    else tray_state._on_selected_device_turn_off_clicked
                ),
                enabled=controls_available,
            ),
        ]

    hardware_mode_menu = pystray.Menu(*hardware_mode_items)

    return [
        *header_items,
        pystray.Menu.SEPARATOR,
        selected_brightness_item,
        *([item("Lighting Profiles", perkey_menu)] if perkey_menu is not None else []),
        pystray.Menu.SEPARATOR,
        item("Hardware Mode", hardware_mode_menu),
        pystray.Menu.SEPARATOR,
        item("Software Effects", sw_effects_menu),
        item("Effect Speed", speed_menu),
        pystray.Menu.SEPARATOR,
        # power mode / settings
        *([item("Power Mode", power_menu)] if power_menu is not None else []),
        item("Support Tools…", tray_state._on_support_debug_clicked),
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

    tray_state = _reloadable_menu_tray(tray)
    tray_state.config.reload()
    return pystray.Menu(*build_menu_items(tray, pystray=pystray, item=item))
