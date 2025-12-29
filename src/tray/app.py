#!/usr/bin/env python3
"""KeyRGB tray app implementation.

Kept as a single importable entrypoint for:
- `python -m src.gui.tray` (packaged launcher)
- legacy `src/tray_app.py`

The heavy lifting lives here; legacy entrypoints delegate to avoid duplication.
"""

from __future__ import annotations

import logging
import os
import sys

from src.core import tcc_power_profiles
from src.core.backends.registry import select_backend
from src.core.diagnostics import collect_diagnostics, format_diagnostics_text

from .dependencies import load_tray_dependencies
from .effect_selection import apply_effect_selection
from .gui_launch import launch_perkey_gui, launch_power_gui, launch_tcc_profiles_gui, launch_uniform_gui
from .ite_dimensions import load_ite_dimensions

from . import icon as icon_mod
from . import menu as menu_mod
from . import polling
from . import runtime

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

        polling.start_hardware_polling(self)
        polling.start_config_polling(self, ite_num_rows=self._ite_rows, ite_num_cols=self._ite_cols)
        polling.start_icon_color_polling(self)

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

    # ---- effect application

    def _start_current_effect(self):
        try:
            if self.config.effect == 'perkey':
                self.engine.stop()
                if self.config.brightness == 0:
                    self.engine.turn_off()
                    self.is_off = True
                    return

                with self.engine.kb_lock:
                    self.engine.kb.set_key_colors(self.config.per_key_colors, brightness=self.config.brightness, enable_user_mode=True)
                self.is_off = False
                return

            if self.config.effect == 'none':
                self.engine.stop()
                if self.config.brightness == 0:
                    self.engine.turn_off()
                    self.is_off = True
                    return

                with self.engine.kb_lock:
                    self.engine.kb.set_color(self.config.color, brightness=self.config.brightness)
                self.is_off = False
                return

            self.engine.start_effect(
                self.config.effect,
                speed=self.config.speed,
                brightness=self.config.brightness,
                color=self.config.color,
            )
            self.is_off = False
        except Exception as e:
            self._log_exception("Error starting effect: %s", e)

    # ---- menu callbacks

    def _on_effect_clicked(self, _icon, item):
        effect_name = menu_mod.normalize_effect_label(item)

        apply_effect_selection(self, effect_name=effect_name)

        self._update_icon()
        self._update_menu()

    def _on_speed_clicked(self, _icon, item):
        speed_str = str(item).replace('🔘', '').replace('⚪', '').strip()
        try:
            self.config.speed = int(speed_str)
            if not self.is_off:
                self._start_current_effect()
            self._update_menu()
        except ValueError:
            pass

    def _on_brightness_clicked(self, _icon, item):
        brightness_str = str(item).replace('🔘', '').replace('⚪', '').strip()
        try:
            brightness = int(brightness_str)
            brightness_hw = brightness * 5

            if brightness_hw > 0:
                self._last_brightness = brightness_hw

            self.config.brightness = brightness_hw
            self.engine.set_brightness(self.config.brightness)
            if not self.is_off:
                self._start_current_effect()
            self._update_menu()
        except ValueError:
            pass

    def _on_off_clicked(self, _icon, _item):
        self.engine.turn_off()
        self.is_off = True
        self._update_icon()
        self._update_menu()

    def _on_turn_on_clicked(self, _icon, _item):
        self.is_off = False

        if self.config.brightness == 0:
            self.config.brightness = self._last_brightness if self._last_brightness > 0 else 25

        if self.config.effect == 'none':
            with self.engine.kb_lock:
                self.engine.kb.set_color(self.config.color, brightness=self.config.brightness)
        else:
            self._start_current_effect()

        self._update_icon()
        self._update_menu()

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
        self._power_forced_off = True
        self.is_off = True
        self.engine.turn_off()
        self._update_icon()
        self._update_menu()

    def restore(self):
        if self._power_forced_off:
            self._power_forced_off = False
            self.is_off = False

            if self.config.brightness == 0:
                self.config.brightness = self._last_brightness if self._last_brightness > 0 else 25

            self._start_current_effect()
            self._update_icon()
            self._update_menu()
            return

        if not self.is_off:
            self._start_current_effect()

    def apply_brightness_from_power_policy(self, brightness: int) -> None:
        """Best-effort brightness apply used by PowerManager battery-saver.

        This must never crash the tray.
        """

        try:
            brightness = int(brightness)
        except Exception:
            return

        if brightness < 0:
            return

        # If the user explicitly turned the keyboard off, don't fight it.
        if self.is_off:
            return

        try:
            if brightness > 0:
                self._last_brightness = brightness
            self.config.brightness = brightness
            self.engine.set_brightness(self.config.brightness)
            self._start_current_effect()
            self._update_menu()
            self._update_icon()
        except Exception:
            # Best-effort only.
            return

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
        if not logging.getLogger().handlers:
            level = logging.DEBUG if os.environ.get('KEYRGB_DEBUG') else logging.INFO
            logging.basicConfig(level=level, format='%(levelname)s %(name)s: %(message)s')

        if os.environ.get("KEYRGB_DEBUG"):
            try:
                diag = collect_diagnostics(include_usb=True)
                logger.debug("Startup diagnostics (Tongfang):\n%s", format_diagnostics_text(diag))
            except Exception:
                # Best-effort; never fail startup because of diagnostics.
                pass

        if not runtime.acquire_single_instance_lock():
            logger.error("KeyRGB is already running (lock held). Not starting a second instance.")
            sys.exit(0)

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
