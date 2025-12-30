#!/usr/bin/env python3
"""KeyRGB tray app implementation.

Kept as a single importable entrypoint for:
- `python -m src.gui.tray` (packaged launcher)
- legacy `src/tray_app.py`

The heavy lifting lives here; legacy entrypoints delegate to avoid duplication.
"""

from __future__ import annotations

import logging
import sys

from src.core import tcc_power_profiles
from src.core.backends.registry import select_backend

from .dependencies import load_tray_dependencies
from .effect_selection import apply_effect_selection
from .gui_launch import launch_perkey_gui, launch_power_gui, launch_tcc_profiles_gui, launch_uniform_gui
from .ite_dimensions import load_ite_dimensions
from .lighting_controller import (
    apply_brightness_from_power_policy,
    on_brightness_clicked,
    on_speed_clicked,
    power_restore,
    power_turn_off,
    start_current_effect,
    turn_off,
    turn_on,
)

from . import icon as icon_mod
from . import menu as menu_mod
from . import polling
from . import runtime
from .startup import acquire_single_instance_or_exit, configure_logging, log_startup_diagnostics_if_debug

logger = logging.getLogger(__name__)


class KeyRGBTray:
    """System tray application for KeyRGB."""

    def __init__(self):
        EffectsEngine, Config, PowerManager = load_tray_dependencies()

        self.config = Config()
        self.engine = EffectsEngine()
        self.icon = None
        self.is_off = False
        self._power_forced_off = False
        self._user_forced_off = False
        self._idle_forced_off = False
        self._last_brightness = 25

        # Backend selection is used for capability-driven UI gating.
        self.backend = select_backend()
        try:
            self.backend_caps = self.backend.capabilities() if self.backend is not None else None
        except Exception:
            self.backend_caps = None

        self._ite_rows, self._ite_cols = load_ite_dimensions()

        self.power_manager = PowerManager(self, config=self.config)
        self.power_manager.start_monitoring()

        polling.start_all_polling(self, ite_num_rows=self._ite_rows, ite_num_cols=self._ite_cols)

        if getattr(self.config, "autostart", False) and not self.is_off:
            self._start_current_effect()

    # ---- logging helpers

    def _log_exception(self, msg: str, exc: Exception):
        logger.exception(msg, exc)

    # ---- icon

    def _update_icon(self):
        if self.icon:
            color = icon_mod.representative_color(config=self.config, is_off=self.is_off)
            self.icon.icon = icon_mod.create_icon(color)

    # ---- menu

    def _update_menu(self):
        if self.icon:
            self.config.reload()
            pystray, item = runtime.get_pystray()
            self.icon.menu = menu_mod.build_menu(self, pystray=pystray, item=item)

    def _refresh_ui(self) -> None:
        """Refresh both icon and menu.

        Convenience wrapper to keep call sites small.
        """

        self._update_icon()
        self._update_menu()

    # ---- effect application

    def _start_current_effect(self):
        start_current_effect(self)

    # ---- menu callbacks

    def _on_effect_clicked(self, _icon, item):
        effect_name = menu_mod.normalize_effect_label(item)

        apply_effect_selection(self, effect_name=effect_name)

        self._refresh_ui()

    def _on_speed_clicked(self, _icon, item):
        on_speed_clicked(self, item)

    def _on_brightness_clicked(self, _icon, item):
        on_brightness_clicked(self, item)

    def _on_off_clicked(self, _icon, _item):
        turn_off(self)

    def _on_turn_on_clicked(self, _icon, _item):
        turn_on(self)

    def _on_perkey_clicked(self, _icon, _item):
        launch_perkey_gui()

    def _on_tuxedo_gui_clicked(self, _icon, _item):
        launch_uniform_gui()

    def _on_power_settings_clicked(self, _icon, _item):
        launch_power_gui()

    def _on_tcc_profiles_gui_clicked(self, _icon, _item):
        launch_tcc_profiles_gui()

    def _on_tcc_profile_clicked(self, profile_id: str) -> None:
        """Switch TUXEDO Control Center power profile (temporary) via DBus."""

        try:
            tcc_power_profiles.set_temp_profile_by_id(profile_id)
        finally:
            # Reflect updated active profile state.
            self._update_menu()

    def _on_quit_clicked(self, icon, _item):
        self.power_manager.stop_monitoring()
        self.engine.stop()
        icon.stop()

    # ---- power callbacks (called by power manager)

    def turn_off(self):
        power_turn_off(self)

    def restore(self):
        power_restore(self)

    def apply_brightness_from_power_policy(self, brightness: int) -> None:
        """Best-effort brightness apply used by PowerManager battery-saver.

        This must never crash the tray.
        """

        apply_brightness_from_power_policy(self, brightness)

    # ---- run

    def run(self):
        pystray, item = runtime.get_pystray()

        logger.info("Creating tray icon...")
        self.icon = pystray.Icon(
            'keyrgb',
            icon_mod.create_icon(icon_mod.representative_color(config=self.config, is_off=self.is_off)),
            'KeyRGB',
            menu=menu_mod.build_menu(self, pystray=pystray, item=item),
        )

        logger.info("KeyRGB tray app started")
        logger.info("Current effect: %s", self.config.effect)
        logger.info("Speed: %s, Brightness: %s", self.config.speed, self.config.brightness)
        self.icon.run()


def main():
    try:
        configure_logging()
        log_startup_diagnostics_if_debug()
        acquire_single_instance_or_exit()

        app = KeyRGBTray()
        app.run()

    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)
    except Exception as e:
        logger.exception("Unhandled error: %s", e)
        sys.exit(1)


if __name__ == '__main__':
    main()
