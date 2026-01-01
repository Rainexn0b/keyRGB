"""Tray application class.

This module holds the `KeyRGBTray` class implementation.
"""

from __future__ import annotations

import logging

from .backend import select_backend_with_introspection
from . import callbacks
from .controllers.lighting_controller import (
    apply_brightness_from_power_policy,
    power_restore,
    power_turn_off,
    start_current_effect,
)
from .hw.ite_dimensions import load_ite_dimensions
from .integrations.dependencies import load_tray_dependencies
from .integrations import runtime
from .lifecycle import maybe_autostart_effect, start_all_polling, start_power_monitoring
from .ui import icon as icon_mod
from .ui import menu as menu_mod
from .ui.refresh import update_icon as update_tray_icon
from .ui.refresh import update_menu as update_tray_menu

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
        self._dim_temp_active = False
        self._dim_temp_target_brightness = None
        self._last_brightness = 25

        # Backend selection is used for capability-driven UI gating.
        self.backend, self.backend_probe, self.backend_caps = select_backend_with_introspection()

        self._ite_rows, self._ite_cols = load_ite_dimensions()

        self.power_manager = start_power_monitoring(self, power_manager_cls=PowerManager, config=self.config)
        start_all_polling(self, ite_num_rows=self._ite_rows, ite_num_cols=self._ite_cols)
        maybe_autostart_effect(self)

    # ---- logging helpers

    def _log_exception(self, msg: str, exc: Exception):
        logger.exception(msg, exc)

    # ---- icon

    def _update_icon(self):
        update_tray_icon(self)

    # ---- menu

    def _update_menu(self):
        update_tray_menu(self)

    def _refresh_ui(self) -> None:
        """Refresh both icon and menu.

        Convenience wrapper to keep call sites small.
        """

        # Call the instance methods so unit tests can invoke this unbound on a
        # dummy object (without requiring real tray/icon dependencies).
        self._update_icon()
        self._update_menu()

    # ---- effect application

    def _start_current_effect(self):
        start_current_effect(self)

    # ---- menu callbacks

    def _on_effect_clicked(self, _icon, item):
        callbacks.on_effect_clicked(self, item)

    def _on_speed_clicked(self, _icon, item):
        callbacks.on_speed_clicked_cb(self, item)

    def _on_brightness_clicked(self, _icon, item):
        callbacks.on_brightness_clicked_cb(self, item)

    def _on_off_clicked(self, _icon, _item):
        callbacks.on_off_clicked(self)

    def _on_turn_on_clicked(self, _icon, _item):
        callbacks.on_turn_on_clicked(self)

    def _on_perkey_clicked(self, _icon, _item):
        callbacks.on_perkey_clicked()

    def _on_tuxedo_gui_clicked(self, _icon, _item):
        callbacks.on_uniform_gui_clicked()

    def _on_power_settings_clicked(self, _icon, _item):
        callbacks.on_power_settings_clicked()

    def _on_tcc_profiles_gui_clicked(self, _icon, _item):
        callbacks.on_tcc_profiles_gui_clicked()

    def _on_tcc_profile_clicked(self, profile_id: str) -> None:
        callbacks.on_tcc_profile_clicked(self, profile_id)

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
            "keyrgb",
            icon_mod.create_icon(icon_mod.representative_color(config=self.config, is_off=self.is_off)),
            "KeyRGB",
            menu=menu_mod.build_menu(self, pystray=pystray, item=item),
        )

        logger.info("KeyRGB tray app started")
        logger.info("Current effect: %s", self.config.effect)
        logger.info("Speed: %s, Brightness: %s", self.config.speed, self.config.brightness)
        self.icon.run()
