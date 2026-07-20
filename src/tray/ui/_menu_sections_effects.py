"""Builders for the effects / speed / brightness tray submenus.

Extracted from ``menu.py`` (WS1 / A8 slice 1) so ``build_menu_items`` becomes
a thin orchestrator over named section builders instead of a 260-line
monolith. The parent module calls these builders directly; there is no
backward-compat re-export because the builders are newly-factored, not
previously public.

Follows the same pattern as ``_menu_sections_profile_power.py``:
- Builders receive ``tray`` / ``tray_state``, ``pystray``, and ``item`` plus
  any per-section context they cannot derive themselves.
- Each builder returns a ``pystray.Menu`` (or compatible object).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import src.core.effects.catalog as effects_catalog
from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE

from ..controllers import software_target_controller
from . import _menu_callbacks as menu_callbacks


class _MenuFactoryProtocol(Protocol):
    SEPARATOR: object

    def __call__(self, *items: object) -> object: ...


class _PystrayProtocol(Protocol):
    Menu: _MenuFactoryProtocol


class _ItemFactoryProtocol(Protocol):
    def __call__(self, text: str, action: object | None = None, **kwargs: object) -> object: ...


class _MenuConfigProtocol(Protocol):
    effect: object
    speed: int
    brightness: int
    software_effect_target: object


_MenuAction = Callable[[object, object], None]


class _MenuTrayProtocol(Protocol):
    config: _MenuConfigProtocol
    is_off: bool
    _on_reactive_color_clicked: _MenuAction
    _on_speed_clicked: _MenuAction
    _on_brightness_clicked: _MenuAction

    def _on_effect_key_clicked(self, effect: str) -> None: ...

    def _on_software_effect_target_clicked(self, target_key: str) -> None: ...


def build_hw_effects_menu(
    tray_state: _MenuTrayProtocol,
    *,
    pystray: _PystrayProtocol,
    item: _ItemFactoryProtocol,
    hw_mode: bool,
    hw_effect_names: tuple[str, ...],
) -> object:
    """Hardware (firmware) animated-effects submenu.

    Greyed out when the tray is in software mode (``hw_mode=False``) so users
    cannot toggle animated hardware effects while a software effect owns the
    deck.
    """

    return pystray.Menu(
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


def build_sw_effects_menu(
    tray: _MenuTrayProtocol,
    *,
    pystray: _PystrayProtocol,
    item: _ItemFactoryProtocol,
    sw_mode: bool,
) -> object:
    """Software-effects submenu (per-key static, animated SW effects, reactive).

    ``sw_items`` builds the base list; if compatible auxiliary devices are
    available, the trailing ``Include enabled lighting areas`` toggle is
    appended so software fan-out can be controlled per session.

    The ``tray`` argument satisfies both the duck-typed menu-callback seam
    (``tray._on_reactive_color_clicked`` etc.) and the auxiliary-device
    capability query (``software_effect_target_has_compatible_devices``).
    """

    secondary_effect_target_supported = software_target_controller.software_effect_target_has_compatible_devices(tray)

    sw_items = [
        item(
            "Reactive Typing Settings…",
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

    if secondary_effect_target_supported:
        sw_items.extend(
            [
                pystray.Menu.SEPARATOR,
                item(
                    "Include enabled lighting areas",
                    menu_callbacks.toggle_enabled_lighting_areas_callback(tray),
                    checked=menu_callbacks.checked_software_target(
                        tray,
                        SOFTWARE_EFFECT_TARGET_ALL_UNIFORM_CAPABLE,
                    ),
                ),
            ]
        )

    return pystray.Menu(*sw_items)


def build_speed_menu(
    tray_state: _MenuTrayProtocol,
    *,
    pystray: _PystrayProtocol,
    item: _ItemFactoryProtocol,
) -> object:
    """Effect-speed submenu (0..10)."""

    return pystray.Menu(
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


def build_brightness_menu(
    tray_state: _MenuTrayProtocol,
    *,
    pystray: _PystrayProtocol,
    item: _ItemFactoryProtocol,
) -> object:
    """Keyboard brightness submenu (0..50 in steps of 5)."""

    return pystray.Menu(
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


__all__ = [
    "build_brightness_menu",
    "build_hw_effects_menu",
    "build_speed_menu",
    "build_sw_effects_menu",
]
