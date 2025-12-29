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
        # Per-key colors stored as {"row,col": [r,g,b]}
        'per_key_colors': {}
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

    @property
    def per_key_colors(self) -> dict:
        """Per-key color map as {(row,col): (r,g,b)}."""
        return self._deserialize_per_key_colors(self._settings.get('per_key_colors', {}))

    @per_key_colors.setter
    def per_key_colors(self, value: dict):
        self._settings['per_key_colors'] = self._serialize_per_key_colors(value or {})
        self._save()
