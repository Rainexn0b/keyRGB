from __future__ import annotations

from typing import Any

from src.core import tcc_power_profiles


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

    # Keep a best-effort view of whether the keyboard device is available.
    try:
        ensure = getattr(getattr(tray, "engine", None), "_ensure_device_available", None)
        if callable(ensure):
            ensure()
    except Exception:
        pass

    device_available = bool(getattr(getattr(tray, "engine", None), "device_available", True))

    def _make_tcc_profile_callback(profile_id: str):
        def _cb(_icon, _item):
            try:
                tray._on_tcc_profile_clicked(profile_id)
            except Exception:
                pass

        return _cb

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
            for effect in ['static', 'pulse', 'strobe', 'fire', 'random', 'perkey_breathing', 'perkey_pulse']
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
    tcc_profiles_menu = None
    try:
        profiles = tcc_power_profiles.list_profiles()
        active = tcc_power_profiles.get_active_profile()
        if profiles:
            profiles_items = [
                item(
                    p.name,
                    _make_tcc_profile_callback(p.id),
                    checked=lambda _i, pid=p.id: (active is not None and active.id == pid),
                    radio=True,
                )
                for p in profiles
            ]
            tcc_profiles_menu = pystray.Menu(
                item('Open Power Profiles…', tray._on_tcc_profiles_gui_clicked),
                pystray.Menu.SEPARATOR,
                item('Activate profile temporarily', pystray.Menu(*profiles_items)),
            )
    except Exception:
        tcc_profiles_menu = None

    return [
        *(
            [
                item(
                    '⚠ Keyboard device not detected',
                    lambda _icon, _item: None,
                    enabled=False,
                ),
                pystray.Menu.SEPARATOR,
            ]
            if not device_available
            else []
        ),
        item('🎨 Hardware Effects', hw_effects_menu),
        item('💫 Software Effects', sw_effects_menu),
        pystray.Menu.SEPARATOR,
        item('⚡ Speed', speed_menu),
        item('💡 Brightness', brightness_menu),
        pystray.Menu.SEPARATOR,
        *([item('🧩 Power Profiles', tcc_profiles_menu)] if tcc_profiles_menu is not None else []),
        item('🔋 Power Management', tray._on_power_settings_clicked),
        item('🎹 Per-Key Colors', tray._on_perkey_clicked),
        item('🌈 Uniform Color', tray._on_tuxedo_gui_clicked),
        pystray.Menu.SEPARATOR,
        item(
            '🔌 Off' if not tray.is_off else '✅ Turn On',
            tray._on_off_clicked if not tray.is_off else tray._on_turn_on_clicked,
            checked=lambda _i: tray.is_off,
        ),
        item('❌ Quit', tray._on_quit_clicked),
    ]


def build_menu(tray: Any, *, pystray: Any, item: Any) -> Any:
    """Build a pystray.Menu object."""

    tray.config.reload()
    return pystray.Menu(*build_menu_items(tray, pystray=pystray, item=item))
