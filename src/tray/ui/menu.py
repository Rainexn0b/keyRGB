from __future__ import annotations

import logging
from typing import Any

from src.core import tcc_power_profiles

from .menu_sections import (
    build_perkey_profiles_menu,
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
        'static': '⚫',
        'pulse': '💗',
        'strobe': '⚡',
        'fire': '🔥',
        'random': '🎲',
        'perkey_breathing': '🌬️',
        'perkey_pulse': '💓',
    }

    hw_effects_menu = pystray.Menu(
        item(
            "⏹️ None",
            tray._on_effect_clicked,
            checked=lambda _i: tray.config.effect == 'none' and not tray.is_off,
            radio=True,
        ),
        pystray.Menu.SEPARATOR,
        *[
            item(
                f"{hw_effect_icons.get(effect, '•')} {effect.capitalize()}",
                tray._on_effect_clicked,
                checked=lambda _i, e=effect: tray.config.effect == e and not tray.is_off,
                radio=True,
            )
            for effect in ['rainbow', 'breathing', 'wave', 'ripple', 'marquee', 'raindrop', 'aurora', 'fireworks']
        ],
    )

    sw_effect_names = ['static', 'pulse', 'strobe', 'fire', 'random']
    if per_key_supported:
        sw_effect_names += ['perkey_breathing', 'perkey_pulse']

    sw_effects_menu = pystray.Menu(
        item(
            "⏹️ None",
            tray._on_effect_clicked,
            checked=lambda _i: tray.config.effect == 'none' and not tray.is_off,
            radio=True,
        ),
        pystray.Menu.SEPARATOR,
        *[
            item(
                f"{sw_effect_icons.get(effect, '•')} {effect.replace('_', ' ').title()}",
                tray._on_effect_clicked,
                checked=lambda _i, e=effect: tray.config.effect == e and not tray.is_off,
                radio=True,
            )
            for effect in sw_effect_names
        ],
    )

    speed_menu = pystray.Menu(
        *[
            item(
                f"{'🔘' if tray.config.speed == speed else '⚪'} {speed}",
                tray._on_speed_clicked,
                checked=lambda _i, s=speed: tray.config.speed == s,
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
                checked=lambda _i, b=brightness: tray.config.brightness == b * 5,
                radio=True,
            )
            for brightness in range(0, 11)
        ]
    )

    # TUXEDO Control Center power profiles (via DBus). If not available, hide the submenu.
    tcc_profiles_menu = build_tcc_profiles_menu(tray, pystray=pystray, item=item, tcc=tcc_power_profiles)

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
        *([item('🧩 Power Profiles', tcc_profiles_menu)] if tcc_profiles_menu is not None else []),
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
