#!/usr/bin/env python3
"""
KeyRGB Configuration Manager
Persists settings to JSON file
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from .config_file_storage import load_config_settings, save_config_settings_atomic


logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for KeyRGB"""
    
    CONFIG_DIR = Path.home() / '.config' / 'keyrgb'
    CONFIG_FILE = CONFIG_DIR / 'config.json'
    
    DEFAULTS = {
        'effect': 'rainbow',
        'speed': 4,  # 0-10 UI scale (10 = fastest)
        'brightness': 25,  # 0-50 hardware scale
        'color': [255, 0, 0],  # RGB for static/custom effects
        'autostart': True,
        # OS session autostart (XDG ~/.config/autostart). When enabled, KeyRGB tray
        # should be started automatically on login.
        'os_autostart': False,
        # Power management (lid/suspend)
        'power_management_enabled': True,
        'power_off_on_suspend': True,
        'power_off_on_lid_close': True,
        'power_restore_on_resume': True,
        'power_restore_on_lid_open': True,
        # Battery saver (dim on AC unplug)
        'battery_saver_enabled': False,
        # Uses the same brightness scale as `brightness`.
        'battery_saver_brightness': 25,

        # Power-source lighting profiles (AC vs battery)
        # These default to "enabled" with no brightness override (None).
        # When brightness is None, KeyRGB will keep using the current brightness
        # (and can optionally fall back to battery_saver_* behavior on battery).
        'ac_lighting_enabled': True,
        'ac_lighting_brightness': None,
        'battery_lighting_enabled': True,
        'battery_lighting_brightness': None,
        # Per-key colors stored as {"row,col": [r,g,b]}
        'per_key_colors': {},

        # Screen dim sync (best-effort, DE-specific). When enabled, KeyRGB will
        # react to desktop-driven display dimming by either turning keyboard
        # LEDs off, or dimming them to a temporary brightness.
        'screen_dim_sync_enabled': True,
        # 'off' | 'temp'
        'screen_dim_sync_mode': 'off',
        # 1-50 (same brightness scale as `brightness`). Used when mode == 'temp'.
        'screen_dim_temp_brightness': 5,
    }

    @staticmethod
    def _serialize_per_key_colors(color_map: dict) -> dict:
        """Convert {(row,col): (r,g,b)} -> {"row,col": [r,g,b]} for JSON."""
        out = {}
        for (row, col), color in color_map.items():
            try:
                r, g, b = color
                out[f"{int(row)},{int(col)}"] = [int(r), int(g), int(b)]
            except Exception:
                continue
        return out

    @staticmethod
    def _deserialize_per_key_colors(data: dict) -> dict:
        """Convert {"row,col": [r,g,b]} -> {(row,col): (r,g,b)}."""
        out = {}
        if not isinstance(data, dict):
            return out
        for k, v in data.items():
            try:
                row_s, col_s = str(k).split(',', 1)
                row = int(row_s.strip())
                col = int(col_s.strip())
                r, g, b = v
                out[(row, col)] = (int(r), int(g), int(b))
            except Exception:
                continue
        return out
    
    def __init__(self):
        """Load configuration"""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        loaded = self._load()
        self._settings = loaded if loaded is not None else self.DEFAULTS.copy()
    
    def _load(self, *, retries: int = 3, retry_delay: float = 0.02):
        """Load settings from file.

        This may race with writers (tray/GUI) updating the JSON file. We retry a few
        times for transient JSONDecodeError (e.g., if a writer truncated then rewrote).
        Returns None if loading fails after retries.
        """

        return load_config_settings(
            config_file=self.CONFIG_FILE,
            defaults=self.DEFAULTS,
            retries=retries,
            retry_delay=retry_delay,
            logger=logger,
        )
    
    def reload(self):
        """Reload settings from file (e.g., after external changes)"""
        loaded = self._load()
        # If the file was transiently unreadable, keep the previous in-memory settings.
        if loaded is not None:
            self._settings = loaded
    
    def _save(self):
        """Save settings to file"""
        save_config_settings_atomic(
            config_dir=self.CONFIG_DIR,
            config_file=self.CONFIG_FILE,
            settings=self._settings,
            logger=logger,
        )
    
    @property
    def effect(self) -> str:
        return self._settings['effect']
    
    @effect.setter
    def effect(self, value: str):
        self._settings['effect'] = value.lower()
        self._save()
    
    @property
    def speed(self) -> int:
        return self._settings['speed']
    
    @speed.setter
    def speed(self, value: int):
        self._settings['speed'] = max(0, min(10, value))
        self._save()
    
    @property
    def brightness(self) -> int:
        return self._settings['brightness']
    
    @brightness.setter
    def brightness(self, value: int):
        self._settings['brightness'] = max(0, min(50, value))
        self._save()
    
    @property
    def color(self) -> tuple:
        return tuple(self._settings['color'])
    
    @color.setter
    def color(self, value: tuple):
        self._settings['color'] = list(value)
        self._save()
    
    @property
    def autostart(self) -> bool:
        return self._settings['autostart']
    
    @autostart.setter
    def autostart(self, value: bool):
        self._settings['autostart'] = value
        self._save()

    @property
    def os_autostart(self) -> bool:
        return bool(self._settings.get('os_autostart', False))

    @os_autostart.setter
    def os_autostart(self, value: bool):
        self._settings['os_autostart'] = bool(value)
        self._save()

    @property
    def power_management_enabled(self) -> bool:
        return bool(self._settings.get('power_management_enabled', True))

    @power_management_enabled.setter
    def power_management_enabled(self, value: bool):
        self._settings['power_management_enabled'] = bool(value)
        self._save()

    @property
    def power_off_on_suspend(self) -> bool:
        return bool(self._settings.get('power_off_on_suspend', True))

    @power_off_on_suspend.setter
    def power_off_on_suspend(self, value: bool):
        self._settings['power_off_on_suspend'] = bool(value)
        self._save()

    @property
    def power_off_on_lid_close(self) -> bool:
        return bool(self._settings.get('power_off_on_lid_close', True))

    @power_off_on_lid_close.setter
    def power_off_on_lid_close(self, value: bool):
        self._settings['power_off_on_lid_close'] = bool(value)
        self._save()

    @property
    def power_restore_on_resume(self) -> bool:
        return bool(self._settings.get('power_restore_on_resume', True))

    @power_restore_on_resume.setter
    def power_restore_on_resume(self, value: bool):
        self._settings['power_restore_on_resume'] = bool(value)
        self._save()

    @property
    def power_restore_on_lid_open(self) -> bool:
        return bool(self._settings.get('power_restore_on_lid_open', True))

    @power_restore_on_lid_open.setter
    def power_restore_on_lid_open(self, value: bool):
        self._settings['power_restore_on_lid_open'] = bool(value)
        self._save()

    # ---- battery saver (legacy)

    @property
    def battery_saver_enabled(self) -> bool:
        return bool(self._settings.get('battery_saver_enabled', False))

    @battery_saver_enabled.setter
    def battery_saver_enabled(self, value: bool):
        self._settings['battery_saver_enabled'] = bool(value)
        self._save()

    @property
    def battery_saver_brightness(self) -> int:
        try:
            return max(0, min(50, int(self._settings.get('battery_saver_brightness', 25) or 0)))
        except Exception:
            return 25

    @battery_saver_brightness.setter
    def battery_saver_brightness(self, value: int):
        self._settings['battery_saver_brightness'] = max(0, min(50, int(value)))
        self._save()

    # ---- power-source lighting profiles

    @property
    def ac_lighting_enabled(self) -> bool:
        return bool(self._settings.get('ac_lighting_enabled', True))

    @ac_lighting_enabled.setter
    def ac_lighting_enabled(self, value: bool):
        self._settings['ac_lighting_enabled'] = bool(value)
        self._save()

    @property
    def ac_lighting_brightness(self) -> int | None:
        v = self._settings.get('ac_lighting_brightness', None)
        if v is None:
            return None
        try:
            return max(0, min(50, int(v)))
        except Exception:
            return None

    @ac_lighting_brightness.setter
    def ac_lighting_brightness(self, value: int | None):
        if value is None:
            self._settings['ac_lighting_brightness'] = None
        else:
            self._settings['ac_lighting_brightness'] = max(0, min(50, int(value)))
        self._save()

    @property
    def battery_lighting_enabled(self) -> bool:
        return bool(self._settings.get('battery_lighting_enabled', True))

    @battery_lighting_enabled.setter
    def battery_lighting_enabled(self, value: bool):
        self._settings['battery_lighting_enabled'] = bool(value)
        self._save()

    @property
    def battery_lighting_brightness(self) -> int | None:
        v = self._settings.get('battery_lighting_brightness', None)
        if v is None:
            return None
        try:
            return max(0, min(50, int(v)))
        except Exception:
            return None

    @battery_lighting_brightness.setter
    def battery_lighting_brightness(self, value: int | None):
        if value is None:
            self._settings['battery_lighting_brightness'] = None
        else:
            self._settings['battery_lighting_brightness'] = max(0, min(50, int(value)))
        self._save()

    @property
    def per_key_colors(self) -> dict:
        """Per-key color map as {(row,col): (r,g,b)}."""
        return self._deserialize_per_key_colors(self._settings.get('per_key_colors', {}))

    @per_key_colors.setter
    def per_key_colors(self, value: dict):
        self._settings['per_key_colors'] = self._serialize_per_key_colors(value or {})
        self._save()

    # ---- screen dim sync

    @property
    def screen_dim_sync_enabled(self) -> bool:
        return bool(self._settings.get('screen_dim_sync_enabled', True))

    @screen_dim_sync_enabled.setter
    def screen_dim_sync_enabled(self, value: bool):
        self._settings['screen_dim_sync_enabled'] = bool(value)
        self._save()

    @property
    def screen_dim_sync_mode(self) -> str:
        mode = str(self._settings.get('screen_dim_sync_mode', 'off') or 'off').strip().lower()
        return mode if mode in {'off', 'temp'} else 'off'

    @screen_dim_sync_mode.setter
    def screen_dim_sync_mode(self, value: str):
        mode = str(value or 'off').strip().lower()
        self._settings['screen_dim_sync_mode'] = mode if mode in {'off', 'temp'} else 'off'
        self._save()

    @property
    def screen_dim_temp_brightness(self) -> int:
        try:
            v = int(self._settings.get('screen_dim_temp_brightness', 5) or 0)
        except Exception:
            v = 5
        # Temp brightness is intended to be non-zero; allow 1..50.
        return max(1, min(50, v))

    @screen_dim_temp_brightness.setter
    def screen_dim_temp_brightness(self, value: int):
        try:
            v = int(value)
        except Exception:
            v = 5
        self._settings['screen_dim_temp_brightness'] = max(1, min(50, v))
        self._save()
