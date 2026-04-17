from __future__ import annotations

import logging
import re
from collections.abc import Callable
from typing import Protocol, cast

import src.core.effects.catalog as effects_catalog
import src.core.power.system as system_power
import src.core.power.tcc_profiles as tcc_power_profiles

from ..controllers import software_target_controller
from . import _menu_callbacks as menu_callbacks
from . import menu_sections, menu_status


logger = logging.getLogger(__name__)
_RECOVERABLE_SYSTEM_POWER_STATUS_ERRORS = (AttributeError, LookupError, OSError, RuntimeError, TypeError, ValueError)

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
    _on_support_debug_clicked: _MenuAction
    _on_power_settings_clicked: _MenuAction
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


def _tcc_profiles_provider() -> menu_sections._TccProfilesProviderProtocol:
    return cast(menu_sections._TccProfilesProviderProtocol, tcc_power_profiles)


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
    caps = getattr(tray_state, "backend_caps", None)
    per_key_supported = bool(getattr(caps, "per_key", True)) if caps is not None else True
    hw_effects_supported = bool(getattr(caps, "hardware_effects", True)) if caps is not None else True
    color_supported = bool(getattr(caps, "color", True)) if caps is not None else True

    menu_status.probe_device_available(tray)

    # Determine current mode for lockdown logic
    sw_mode = menu_status.is_software_mode(tray)
    hw_mode = menu_status.is_hardware_mode(tray)

    device_entries = menu_status.device_context_entries(tray)
    selected_context = menu_status.selected_device_context_entry(tray)

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

    software_target_menu = pystray.Menu(
        *[
            item(
                str(option.get("label") or "Keyboard Only"),
                menu_callbacks.software_target_callback(tray_state, str(option.get("key") or "keyboard")),
                checked=menu_callbacks.checked_software_target(tray_state, str(option.get("key") or "keyboard")),
                enabled=bool(option.get("enabled", True)),
                radio=True,
            )
            for option in software_target_controller.software_effect_target_options(tray)
        ]
    )

    # TUXEDO Control Center power profiles (via DBus). If not available, hide the submenu.
    tcc_profiles_menu = menu_sections.build_tcc_profiles_menu(
        cast(menu_sections._TccProfilesTrayProtocol, tray),
        pystray=pystray,
        item=item,
        tcc=_tcc_profiles_provider(),
    )

    # Lightweight system power mode toggle (cpufreq sysfs). If not available, hide.
    system_power_menu = menu_sections.build_system_power_mode_menu(
        cast(menu_sections._SystemPowerMenuTrayProtocol, tray),
        pystray=pystray,
        item=item,
    )

    # Avoid collisions: only show one power-control menu.
    system_power_can_apply = False
    try:
        st = system_power.get_status()
        system_power_can_apply = bool(st.supported and st.identifiers.get("can_apply") == "true")
    except _RECOVERABLE_SYSTEM_POWER_STATUS_ERRORS:  # @quality-exception exception-transparency: system power status read is a runtime probe boundary; failure degrades to hiding the menu item
        system_power_can_apply = False

    perkey_menu = menu_sections.build_perkey_profiles_menu(
        cast(menu_sections._PerkeyMenuTrayProtocol, tray),
        pystray=pystray,
        item=item,
        per_key_supported=per_key_supported,
    )
    # Choose which power menu to show as "Power Mode".
    # Prefer system power when it can apply; otherwise fall back to TCC if present.
    power_menu = None
    if system_power_menu is not None and system_power_can_apply:
        power_menu = system_power_menu
    elif tcc_profiles_menu is not None:
        power_menu = tcc_profiles_menu
    elif system_power_menu is not None:
        power_menu = system_power_menu

    header_items = [
        item(
            str(entry.get("text") or menu_status.keyboard_status_text(tray)),
            menu_callbacks.device_context_callback(tray_state, str(entry.get("key") or "keyboard")),
            checked=menu_callbacks.checked_device_context(selected_context, str(entry.get("key") or "keyboard")),
            radio=True,
        )
        for entry in device_entries
    ]

    if str(selected_context.get("device_type") or "keyboard") != "keyboard":
        return [
            *header_items,
            pystray.Menu.SEPARATOR,
            *menu_sections.build_device_context_menu_items(
                cast(menu_sections._DeviceContextMenuTrayProtocol, tray),
                pystray=pystray,
                item=item,
                context_entry=selected_context,
            ),
        ]

    return [
        *header_items,
        pystray.Menu.SEPARATOR,
        # === HARDWARE MODE ===
        item(
            "Hardware Static Mode",
            tray_state._on_hardware_static_mode_clicked,
            checked=menu_callbacks.checked_hw_static(tray_state, hw_mode=hw_mode),
        ),
        *(
            [
                item(
                    "Hardware Uniform Color…",
                    tray_state._on_hardware_color_clicked,
                )
            ]
            if color_supported
            else []
        ),
        *(
            [
                item(
                    hw_effects_label,
                    hw_effects_menu,
                    enabled=bool(hw_effect_names),
                    # Menu always enabled, individual animated effects locked when in SW mode
                )
            ]
            if hw_effects_supported
            else []
        ),
        pystray.Menu.SEPARATOR,
        # === SOFTWARE MODE ===
        # Per-key profiles + SW effects
        *([item("Software Color Editor", perkey_menu)] if perkey_menu is not None else []),
        item("Software Effects", sw_effects_menu),
        item("Software Targets", software_target_menu),
        pystray.Menu.SEPARATOR,
        # === COMMON CONTROLS ===
        item("Effect Speed", speed_menu),
        item("Brightness Override", brightness_menu),
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
