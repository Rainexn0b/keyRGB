from __future__ import annotations

import logging
import re
from typing import Any

import src.core.power.tcc_profiles as tcc_power_profiles
import src.core.effects.catalog as effects_catalog
import src.core.power.system as system_power

from ..controllers import software_target_controller
from . import _menu_callbacks as menu_callbacks
from . import menu_sections, menu_status


logger = logging.getLogger(__name__)


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


def build_menu_items(tray: Any, *, pystray: Any, item: Any) -> list[Any]:
    """Build menu items list for dynamic menu updates."""

    caps = getattr(tray, "backend_caps", None)
    per_key_supported = bool(getattr(caps, "per_key", True)) if caps is not None else True
    hw_effects_supported = bool(getattr(caps, "hardware_effects", True)) if caps is not None else True
    color_supported = bool(getattr(caps, "color", True)) if caps is not None else True

    menu_status.probe_device_available(tray)

    # Determine current mode for lockdown logic
    sw_mode = menu_status.is_software_mode(tray)
    hw_mode = menu_status.is_hardware_mode(tray)

    device_entries = menu_status.device_context_entries(tray)
    selected_context = menu_status.selected_device_context_entry(tray)

    hw_effect_names = effects_catalog.detected_backend_hw_effect_names(getattr(tray, "backend", None))
    hw_effects_label = menu_status.hardware_effects_menu_text(tray)

    # HW effects menu - animated effects lock when in SW mode.
    # Switching back to static hardware mode is now a separate top-level action.
    hw_effects_menu = pystray.Menu(
        *[
            item(
                effects_catalog.title_for_effect(effect),
                menu_callbacks.effect_key_callback(tray, effects_catalog.hardware_effect_selection_key(effect)),
                checked=menu_callbacks.checked_hw_effect(
                    tray,
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
            "Reactive Typing Color…",
            tray._on_reactive_color_clicked,
        ),
        pystray.Menu.SEPARATOR,
        item(
            "None (static per-key)",
            menu_callbacks.effect_key_callback(tray, "perkey"),
            checked=menu_callbacks.checked_perkey(tray),
            radio=True,
        ),
        pystray.Menu.SEPARATOR,
        *[
            item(
                effects_catalog.title_for_effect(effect),
                menu_callbacks.effect_key_callback(tray, effect),
                checked=menu_callbacks.checked_sw_effect(tray, effect, sw_mode=sw_mode),
                radio=True,
                enabled=sw_mode,
            )
            for effect in effects_catalog.SOFTWARE_EFFECTS
        ],
        pystray.Menu.SEPARATOR,
        *[
            item(
                effects_catalog.title_for_effect(effect),
                menu_callbacks.effect_key_callback(tray, effect),
                checked=menu_callbacks.checked_sw_effect(tray, effect, sw_mode=sw_mode),
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
                tray._on_speed_clicked,
                checked=menu_callbacks.checked_speed(tray, speed),
                radio=True,
            )
            for speed in range(0, 11)
        ]
    )

    brightness_menu = pystray.Menu(
        *[
            item(
                str(brightness),
                tray._on_brightness_clicked,
                checked=menu_callbacks.checked_brightness(tray, brightness * 5),
                radio=True,
            )
            for brightness in range(0, 11)
        ]
    )

    software_target_menu = pystray.Menu(
        *[
            item(
                str(option.get("label") or "Keyboard Only"),
                menu_callbacks.software_target_callback(tray, str(option.get("key") or "keyboard")),
                checked=menu_callbacks.checked_software_target(tray, str(option.get("key") or "keyboard")),
                enabled=bool(option.get("enabled", True)),
                radio=True,
            )
            for option in software_target_controller.software_effect_target_options(tray)
        ]
    )

    # TUXEDO Control Center power profiles (via DBus). If not available, hide the submenu.
    tcc_profiles_menu = menu_sections.build_tcc_profiles_menu(tray, pystray=pystray, item=item, tcc=tcc_power_profiles)

    # Lightweight system power mode toggle (cpufreq sysfs). If not available, hide.
    system_power_menu = menu_sections.build_system_power_mode_menu(tray, pystray=pystray, item=item)

    # Avoid collisions: only show one power-control menu.
    system_power_can_apply = False
    try:
        st = system_power.get_status()
        system_power_can_apply = bool(st.supported and st.identifiers.get("can_apply") == "true")
    except Exception:  # @quality-exception exception-transparency: system power status read is a runtime probe boundary; failure degrades to hiding the menu item
        system_power_can_apply = False

    perkey_menu = menu_sections.build_perkey_profiles_menu(
        tray,
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
            menu_callbacks.device_context_callback(tray, str(entry.get("key") or "keyboard")),
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
                tray, pystray=pystray, item=item, context_entry=selected_context
            ),
        ]

    return [
        *header_items,
        pystray.Menu.SEPARATOR,
        # === HARDWARE MODE ===
        item(
            "Hardware Static Mode",
            tray._on_hardware_static_mode_clicked,
            checked=menu_callbacks.checked_hw_static(tray, hw_mode=hw_mode),
        ),
        *(
            [
                item(
                    "Hardware Uniform Color…",
                    tray._on_hardware_color_clicked,
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
        item("Support Tools…", tray._on_support_debug_clicked),
        item("Settings", tray._on_power_settings_clicked),
        pystray.Menu.SEPARATOR,
        # off/on / (active mode) / quit
        item(
            "Turn Off" if not tray.is_off else "Turn On",
            tray._on_off_clicked if not tray.is_off else tray._on_turn_on_clicked,
            checked=lambda _i: tray.is_off,
        ),
        item(
            menu_status.tray_lighting_mode_text(tray),
            lambda _icon, _item: None,
            enabled=False,
        ),
        item("Quit", tray._on_quit_clicked),
    ]


def build_menu(tray: Any, *, pystray: Any, item: Any) -> Any:
    """Build a pystray.Menu object."""

    tray.config.reload()
    return pystray.Menu(*build_menu_items(tray, pystray=pystray, item=item))
