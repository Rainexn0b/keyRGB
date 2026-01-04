from __future__ import annotations

import logging
import re
from typing import Any

import src.core.tcc_power_profiles as tcc_power_profiles
from src.core.effects.catalog import (
    HW_EFFECTS,
    REACTIVE_EFFECTS,
    SOFTWARE_EFFECTS,
    normalize_effect_name,
    title_for_effect,
)
from src.core.system_power import get_status as _system_power_status

from .menu_sections import (
    build_perkey_profiles_menu,
    build_system_power_mode_menu,
    build_tcc_profiles_menu,
    is_hardware_mode,
    is_software_mode,
    keyboard_status_text,
    probe_device_available,
    tray_lighting_mode_text,
)


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
    return normalize_effect_name(s)


def build_menu_items(tray: Any, *, pystray: Any, item: Any) -> list[Any]:
    """Build menu items list for dynamic menu updates."""

    caps = getattr(tray, "backend_caps", None)
    per_key_supported = bool(getattr(caps, "per_key", True)) if caps is not None else True
    hw_effects_supported = bool(getattr(caps, "hardware_effects", True)) if caps is not None else True

    probe_device_available(tray)

    # Determine current mode for lockdown logic
    sw_mode = is_software_mode(tray)
    hw_mode = is_hardware_mode(tray)

    def _hw_cb(effect: str):
        def _action(_icon, _item):
            tray._on_effect_key_clicked(effect)

        return _action

    def _checked_effect(effect: str):
        def _checked(_item):
            return tray.config.effect == effect and not tray.is_off

        return _checked

    def _checked_speed(speed: int):
        def _checked(_item):
            return tray.config.speed == speed

        return _checked

    def _checked_brightness(brightness: int):
        def _checked(_item):
            return tray.config.brightness == brightness

        return _checked

    # HW effects menu - "None" always enabled (switches to uniform color mode),
    # animated effects locked when in SW mode
    hw_effects_menu = pystray.Menu(
        item(
            "None (use uniform color)",
            _hw_cb("hw_uniform"),
            checked=lambda _i: (tray.config.effect == "none" and hw_mode and not tray.is_off),
            radio=True,
            # Always enabled - this is how user switches back to HW uniform mode
        ),
        pystray.Menu.SEPARATOR,
        *[
            item(
                title_for_effect(effect),
                _hw_cb(effect),
                checked=_checked_effect(effect),
                radio=True,
                enabled=hw_mode,  # Grey out animated effects when in SW mode
            )
            for effect in HW_EFFECTS
        ],
    )

    def _sw_cb(effect: str):
        def _action(_icon, _item):
            tray._on_effect_key_clicked(effect)

        return _action

    # SW effects work best with per-key colors loaded
    # "None" here means static per-key display, other SW effects locked when in HW mode
    def _checked_perkey(_item):
        return tray.config.effect == "perkey" and not tray.is_off

    sw_items = [
        item(
            "None (static per-key)",
            _sw_cb("perkey"),
            checked=_checked_perkey,
            radio=True,
        ),
        pystray.Menu.SEPARATOR,
        *[
            item(
                title_for_effect(effect),
                _sw_cb(effect),
                checked=_checked_effect(effect),
                radio=True,
                enabled=sw_mode,
            )
            for effect in SOFTWARE_EFFECTS
        ],
        pystray.Menu.SEPARATOR,
        *[
            item(
                title_for_effect(effect),
                _sw_cb(effect),
                checked=_checked_effect(effect),
                radio=True,
                enabled=sw_mode,
            )
            for effect in REACTIVE_EFFECTS
        ],
    ]

    sw_effects_menu = pystray.Menu(*sw_items)

    speed_menu = pystray.Menu(
        *[
            item(
                str(speed),
                tray._on_speed_clicked,
                checked=_checked_speed(speed),
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
                checked=_checked_brightness(brightness * 5),
                radio=True,
            )
            for brightness in range(0, 11)
        ]
    )

    # TUXEDO Control Center power profiles (via DBus). If not available, hide the submenu.
    tcc_profiles_menu = build_tcc_profiles_menu(tray, pystray=pystray, item=item, tcc=tcc_power_profiles)

    # Lightweight system power mode toggle (cpufreq sysfs). If not available, hide.
    system_power_menu = build_system_power_mode_menu(tray, pystray=pystray, item=item)

    # Avoid collisions: only show one power-control menu.
    system_power_can_apply = False
    try:
        st = _system_power_status()
        system_power_can_apply = bool(st.supported and st.identifiers.get("can_apply") == "true")
    except Exception:
        system_power_can_apply = False

    perkey_menu = build_perkey_profiles_menu(tray, pystray=pystray, item=item, per_key_supported=per_key_supported)

    # Choose which power menu to show as "Power Mode".
    # Prefer system power when it can apply; otherwise fall back to TCC if present.
    power_menu = None
    if system_power_menu is not None and system_power_can_apply:
        power_menu = system_power_menu
    elif tcc_profiles_menu is not None:
        power_menu = tcc_profiles_menu
    elif system_power_menu is not None:
        power_menu = system_power_menu

    return [
        item(
            keyboard_status_text(tray),
            lambda _icon, _item: None,
            enabled=False,
        ),
        pystray.Menu.SEPARATOR,
        # === HARDWARE MODE ===
        # HW effects + uniform color picker
        *(
            [
                item(
                    "Hardware Effects",
                    hw_effects_menu,
                    # Menu always enabled, individual animated effects locked when in SW mode
                )
            ]
            if hw_effects_supported
            else []
        ),
        item(
            "Hardware Color",
            tray._on_hardware_color_clicked,
            # Always enabled - this is how user switches to HW uniform color mode
        ),
        pystray.Menu.SEPARATOR,
        # === SOFTWARE MODE ===
        # Per-key profiles + SW effects
        *([item("Software Color Editor", perkey_menu)] if perkey_menu is not None else []),
        item("Software Effects", sw_effects_menu),
        pystray.Menu.SEPARATOR,
        # === COMMON CONTROLS ===
        item("Effect Speed", speed_menu),
        item("Brightness Override", brightness_menu),
        pystray.Menu.SEPARATOR,
        # power mode / settings
        *([item("Power Mode", power_menu)] if power_menu is not None else []),
        item("Settings", tray._on_power_settings_clicked),
        pystray.Menu.SEPARATOR,
        # off/on / (active mode) / quit
        item(
            "Turn Off" if not tray.is_off else "Turn On",
            tray._on_off_clicked if not tray.is_off else tray._on_turn_on_clicked,
            checked=lambda _i: tray.is_off,
        ),
        item(
            tray_lighting_mode_text(tray),
            lambda _icon, _item: None,
            enabled=False,
        ),
        item("Quit", tray._on_quit_clicked),
    ]


def build_menu(tray: Any, *, pystray: Any, item: Any) -> Any:
    """Build a pystray.Menu object."""

    tray.config.reload()
    return pystray.Menu(*build_menu_items(tray, pystray=pystray, item=item))
