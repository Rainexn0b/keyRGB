from __future__ import annotations

import logging
from typing import Any

import src.core.tcc_power_profiles as tcc_power_profiles
from src.core.system_power import get_status as _system_power_status

from .menu_sections import (
    build_perkey_profiles_menu,
    build_system_power_mode_menu,
    build_tcc_profiles_menu,
    keyboard_status_text,
    probe_device_available,
    tray_lighting_mode_text,
)


logger = logging.getLogger(__name__)


_EFFECT_EMOJIS = [
    '🌈', '💨', '🌊', '💧', '✨', '🌧️', '🌌', '🎆',
    '⚫', '💗', '⚡', '🔥', '🎲', '⏹️', '🌬️', '💓',
]


def normalize_effect_label(label: str) -> str:
    name = str(label).lower()
    for emoji in _EFFECT_EMOJIS:
        name = name.replace(emoji, '').strip()
    return name


def build_menu_items(tray: Any, *, pystray: Any, item: Any) -> list[Any]:
    """Build menu items list for dynamic menu updates."""

    caps = getattr(tray, "backend_caps", None)
    per_key_supported = bool(getattr(caps, "per_key", True)) if caps is not None else True
    hw_effects_supported = bool(getattr(caps, "hardware_effects", True)) if caps is not None else True

    device_available = probe_device_available(tray)

    hw_effect_icons = {
        'rainbow': '🌈',
        'breathing': '💨',
        'wave': '🌊',
        'ripple': '💧',
        'marquee': '✨',
        'raindrop': '🌧️',
        'aurora': '🌌',
        'fireworks': '🎆',
    }

    sw_effect_icons = {
        'rainbow_wave': '🌈',
        'rainbow_swirl': '🌀',
        'spectrum_cycle': '🌈',
        'color_cycle': '🎨',
        'chase': '🏃',
        'twinkle': '✨',
        'strobe': '⚡',
        'reactive_fade': '⚡',
        'reactive_ripple': '💧',
        'reactive_rainbow': '🌈',
        'reactive_snake': '🐍',
    }

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

    hw_effects_menu = pystray.Menu(
        item(
            "⏹️ None",
            tray._on_effect_clicked,
            checked=_checked_effect('none'),
            radio=True,
        ),
        pystray.Menu.SEPARATOR,
        *[
            item(
                f"{hw_effect_icons.get(effect, '•')} {effect.capitalize()}",
                tray._on_effect_clicked,
                checked=_checked_effect(effect),
                radio=True,
            )
            for effect in ['rainbow', 'breathing', 'wave', 'ripple', 'marquee', 'raindrop', 'aurora', 'fireworks']
        ],
    )

    def _sw_cb(effect: str):
        def _action(_icon, _item):
            tray._on_effect_key_clicked(effect)

        return _action

    sw_effects_menu = pystray.Menu(
        item(
            "⏹️ None",
            _sw_cb('none'),
            checked=_checked_effect('none'),
            radio=True,
        ),
        pystray.Menu.SEPARATOR,
        item(
            f"{sw_effect_icons.get('rainbow_wave', '•')} Rainbow Wave",
            _sw_cb('rainbow_wave'),
            checked=_checked_effect('rainbow_wave'),
            radio=True,
        ),
        item(
            f"{sw_effect_icons.get('rainbow_swirl', '•')} Rainbow Swirl",
            _sw_cb('rainbow_swirl'),
            checked=_checked_effect('rainbow_swirl'),
            radio=True,
        ),
        item(
            f"{sw_effect_icons.get('spectrum_cycle', '•')} Spectrum Cycle",
            _sw_cb('spectrum_cycle'),
            checked=_checked_effect('spectrum_cycle'),
            radio=True,
        ),
        item(
            f"{sw_effect_icons.get('color_cycle', '•')} Color Cycle",
            _sw_cb('color_cycle'),
            checked=_checked_effect('color_cycle'),
            radio=True,
        ),
        item(
            f"{sw_effect_icons.get('chase', '•')} Chase",
            _sw_cb('chase'),
            checked=_checked_effect('chase'),
            radio=True,
        ),
        item(
            f"{sw_effect_icons.get('twinkle', '•')} Twinkle",
            _sw_cb('twinkle'),
            checked=_checked_effect('twinkle'),
            radio=True,
        ),
        item(
            f"{sw_effect_icons.get('strobe', '•')} Strobe",
            _sw_cb('strobe'),
            checked=_checked_effect('strobe'),
            radio=True,
        ),
        item(
            f"{sw_effect_icons.get('reactive_fade', '•')} Reactive Fade",
            _sw_cb('reactive_fade'),
            checked=_checked_effect('reactive_fade'),
            radio=True,
        ),
        item(
            f"{sw_effect_icons.get('reactive_ripple', '•')} Reactive Ripple",
            _sw_cb('reactive_ripple'),
            checked=_checked_effect('reactive_ripple'),
            radio=True,
        ),
        item(
            f"{sw_effect_icons.get('reactive_rainbow', '•')} Reactive Rainbow",
            _sw_cb('reactive_rainbow'),
            checked=_checked_effect('reactive_rainbow'),
            radio=True,
        ),
        item(
            f"{sw_effect_icons.get('reactive_snake', '•')} Reactive Snake",
            _sw_cb('reactive_snake'),
            checked=_checked_effect('reactive_snake'),
            radio=True,
        ),
    )

    speed_menu = pystray.Menu(
        *[
            item(
                f"{'🔘' if tray.config.speed == speed else '⚪'} {speed}",
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
                f"{'🔘' if tray.config.brightness == brightness * 5 else '⚪'} {brightness}",
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

    return [
        item(
            keyboard_status_text(tray),
            lambda _icon, _item: None,
            enabled=False,
        ),
        pystray.Menu.SEPARATOR,
        # Effects section (speed is effect-specific)
        *([item('🎨 Hardware Effects', hw_effects_menu)] if hw_effects_supported else []),
        item('💫 Software Effects', sw_effects_menu),
        item('⚡ Speed', speed_menu),
        pystray.Menu.SEPARATOR,

        # Lighting section (brightness + per-key/uniform)
        item('💡 Brightness', brightness_menu),
        *([item('🎹 Per-key Colors', perkey_menu)] if perkey_menu is not None else []),
        item('🌈 Uniform Color', tray._on_tuxedo_gui_clicked),
        pystray.Menu.SEPARATOR,

        # Power section
        *(
            [item('🔋 Power Mode', system_power_menu)]
            if (system_power_menu is not None and system_power_can_apply)
            else ([] if tcc_profiles_menu is not None else ([item('🔋 Power Mode', system_power_menu)] if system_power_menu is not None else []))
        ),
        *(
            [item('🧩 Power Profiles (TCC)', tcc_profiles_menu)]
            if (tcc_profiles_menu is not None and not system_power_can_apply)
            else []
        ),
        item('⚙ Settings', tray._on_power_settings_clicked),
        pystray.Menu.SEPARATOR,

        item(
            '🔌 Off' if not tray.is_off else '✅ Turn On',
            tray._on_off_clicked if not tray.is_off else tray._on_turn_on_clicked,
            checked=lambda _i: tray.is_off,
        ),
        item(
            tray_lighting_mode_text(tray),
            lambda _icon, _item: None,
            enabled=False,
        ),
        item('❌ Quit', tray._on_quit_clicked),
    ]


def build_menu(tray: Any, *, pystray: Any, item: Any) -> Any:
    """Build a pystray.Menu object."""

    tray.config.reload()
    return pystray.Menu(*build_menu_items(tray, pystray=pystray, item=item))
