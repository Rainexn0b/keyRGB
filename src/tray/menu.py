from __future__ import annotations

import logging
from typing import Any

from src.core import tcc_power_profiles
from src.core.logging_utils import log_throttled


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

    # Keep a best-effort view of whether the keyboard device is available.
    try:
        ensure = getattr(getattr(tray, "engine", None), "_ensure_device_available", None)
        if callable(ensure):
            ensure()
    except Exception as exc:
        log_throttled(
            logger,
            "tray.menu.ensure_device",
            interval_s=60,
            level=logging.DEBUG,
            msg="Failed to ensure device availability",
            exc=exc,
        )

    device_available = bool(getattr(getattr(tray, "engine", None), "device_available", True))

    def _make_tcc_profile_callback(profile_id: str):
        def _cb(_icon, _item):
            try:
                tray._on_tcc_profile_clicked(profile_id)
            except Exception as exc:
                log_throttled(
                    logger,
                    "tray.menu.tcc_profile_click",
                    interval_s=60,
                    level=logging.DEBUG,
                    msg="TCC profile activation callback failed",
                    exc=exc,
                )

        return _cb

    def _make_perkey_profile_callback(profile_name: str):
        def _cb(_icon, _item):
            try:
                from src.core import profiles as core_profiles

                name = core_profiles.set_active_profile(profile_name)
                colors = core_profiles.load_per_key_colors(name)
                core_profiles.apply_profile_to_config(tray.config, colors)

                # If the user explicitly chose a profile, treat it like an effect selection.
                # Respect power manager forced-off state.
                if not getattr(tray, "_power_forced_off", False):
                    tray.is_off = False
                    tray._start_current_effect()

                tray._update_icon()
                tray._update_menu()
            except Exception as exc:
                log_throttled(
                    logger,
                    "tray.menu.perkey_profile_click",
                    interval_s=60,
                    level=logging.DEBUG,
                    msg="Per-key profile activation callback failed",
                    exc=exc,
                )

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
    tcc_profiles_menu = None
    try:
        tcc_profiles = tcc_power_profiles.list_profiles()
        active = tcc_power_profiles.get_active_profile()
        if tcc_profiles:
            profiles_items = [
                item(
                    p.name,
                    _make_tcc_profile_callback(p.id),
                    checked=lambda _i, pid=p.id: (active is not None and active.id == pid),
                    radio=True,
                )
                for p in tcc_profiles
            ]
            tcc_profiles_menu = pystray.Menu(
                item('Open Power Profiles…', tray._on_tcc_profiles_gui_clicked),
                pystray.Menu.SEPARATOR,
                *profiles_items,
            )
    except Exception as exc:
        log_throttled(
            logger,
            "tray.menu.tcc_profiles",
            interval_s=120,
            level=logging.DEBUG,
            msg="Failed to populate TCC profiles menu",
            exc=exc,
        )
        tcc_profiles_menu = None

    perkey_menu = None
    if per_key_supported:
        try:
            from src.core import profiles as core_profiles

            perkey_profiles = core_profiles.list_profiles()
            active_profile = core_profiles.get_active_profile()

            profile_items = [
                item(
                    name,
                    _make_perkey_profile_callback(name),
                    checked=lambda _i, n=name: active_profile == n,
                    radio=True,
                )
                for name in perkey_profiles
            ]

            perkey_menu = pystray.Menu(
                item('Open Color Editor…', tray._on_perkey_clicked),
                pystray.Menu.SEPARATOR,
                *profile_items,
            )
        except Exception as exc:
            log_throttled(
                logger,
                "tray.menu.perkey_profiles",
                interval_s=120,
                level=logging.DEBUG,
                msg="Failed to populate per-key profiles menu",
                exc=exc,
            )
            perkey_menu = pystray.Menu(item('Open Color Editor…', tray._on_perkey_clicked))

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
        # Effects section (speed is effect-specific)
        *([item('🎨 Hardware Effects', hw_effects_menu)] if hw_effects_supported else []),
        item('💫 Software Effects', sw_effects_menu),
        item('⚡ Speed', speed_menu),
        pystray.Menu.SEPARATOR,

        # Lighting section (brightness + per-key/uniform)
        item('💡 Brightness', brightness_menu),
        *([item('🎹 Per-Key Colors', perkey_menu)] if perkey_menu is not None else []),
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
        item('❌ Quit', tray._on_quit_clicked),
    ]


def build_menu(tray: Any, *, pystray: Any, item: Any) -> Any:
    """Build a pystray.Menu object."""

    tray.config.reload()
    return pystray.Menu(*build_menu_items(tray, pystray=pystray, item=item))
