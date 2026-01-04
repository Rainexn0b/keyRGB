#!/usr/bin/env python3
"""KeyRGB Config implementation.

This module contains the `Config` class implementation. The package
`src.core.config` re-exports `Config` for backward compatibility.
"""

from __future__ import annotations

import logging

from .defaults import DEFAULTS as _DEFAULTS
from .file_storage import load_config_settings, save_config_settings_atomic
from .paths import config_dir, config_file_path
from .perkey_colors import deserialize_per_key_colors, serialize_per_key_colors

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for KeyRGB."""

    # Kept for backward compatibility with existing callers.
    CONFIG_DIR = config_dir()
    CONFIG_FILE = config_file_path()

    DEFAULTS = _DEFAULTS

    @staticmethod
    def _serialize_per_key_colors(color_map: dict) -> dict:
        """Convert {(row,col): (r,g,b)} -> {"row,col": [r,g,b]} for JSON."""
        return serialize_per_key_colors(color_map)

    @staticmethod
    def _deserialize_per_key_colors(data: dict) -> dict:
        """Convert {"row,col": [r,g,b]} -> {(row,col): (r,g,b)}."""
        return deserialize_per_key_colors(data)

    def __init__(self):
        """Load configuration."""

        # Recompute at runtime so test harnesses can set env vars in conftest.
        self.CONFIG_DIR = config_dir()
        self.CONFIG_FILE = config_file_path()
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        loaded = self._load()
        self._settings = loaded if loaded is not None else self.DEFAULTS.copy()
        self._coerce_loaded_settings()

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
        """Reload settings from file (e.g., after external changes)."""

        loaded = self._load()
        # If the file was transiently unreadable, keep the previous in-memory settings.
        if loaded is not None:
            self._settings = loaded

    def _save(self):
        """Save settings to file."""

        save_config_settings_atomic(
            config_dir=self.CONFIG_DIR,
            config_file=self.CONFIG_FILE,
            settings=self._settings,
            logger=logger,
        )

    @staticmethod
    def _normalize_brightness_value(value: int) -> int:
        """Normalize brightness for storage.

        Internally, KeyRGB persists brightness on a 0..50 hardware scale.
        The tray UI exposes 0..10 steps, which map to multiples of 5.
        Keeping stored values on that step grid ensures the tray always has
        a selected radio item.
        """

        try:
            v = int(value)
        except Exception:
            return 0

        v = max(0, min(50, v))
        if v == 0:
            return 0

        snapped = int(round(v / 5.0)) * 5
        snapped = max(0, min(50, snapped))
        if snapped == 0:
            snapped = 5
        return snapped

    def _coerce_loaded_settings(self) -> None:
        """Coerce loaded settings into a consistent, UI-compatible shape."""

        try:
            changed = False

            before = self._settings.get("brightness", None)
            after = self._normalize_brightness_value(before if before is not None else 0)
            if before != after:
                self._settings["brightness"] = after
                changed = True

            # Normalize stored power-source brightness overrides when present.
            for key in ("ac_lighting_brightness", "battery_lighting_brightness"):
                raw = self._settings.get(key, None)
                if raw is None:
                    continue
                normalized = self._normalize_brightness_value(raw)
                if raw != normalized:
                    self._settings[key] = int(normalized)
                    changed = True

            if changed:
                self._save()
        except Exception:
            return

    @property
    def effect(self) -> str:
        return self._settings["effect"]

    @effect.setter
    def effect(self, value: str):
        self._settings["effect"] = value.lower()
        self._save()

    @property
    def return_effect_after_effect(self) -> str | None:
        v = self._settings.get("return_effect_after_effect", None)
        if v is None:
            return None
        try:
            s = str(v).strip().lower()
        except Exception:
            return None
        if not s:
            return None
        if s == "perkey":
            return "perkey"
        return None

    @return_effect_after_effect.setter
    def return_effect_after_effect(self, value: str | None):
        if value is None:
            self._settings["return_effect_after_effect"] = None
        else:
            self._settings["return_effect_after_effect"] = str(value).strip().lower() or None
        self._save()

    @property
    def speed(self) -> int:
        return self._settings["speed"]

    @speed.setter
    def speed(self, value: int):
        self._settings["speed"] = max(0, min(10, value))
        self._save()

    @property
    def brightness(self) -> int:
        return self._settings["brightness"]

    @brightness.setter
    def brightness(self, value: int):
        self._settings["brightness"] = self._normalize_brightness_value(value)
        self._save()

    @property
    def color(self) -> tuple:
        return tuple(self._settings["color"])

    @color.setter
    def color(self, value: tuple):
        self._settings["color"] = list(value)
        self._save()

    @property
    def autostart(self) -> bool:
        return self._settings["autostart"]

    @autostart.setter
    def autostart(self, value: bool):
        self._settings["autostart"] = value
        self._save()

    @property
    def os_autostart(self) -> bool:
        return bool(self._settings.get("os_autostart", False))

    @os_autostart.setter
    def os_autostart(self, value: bool):
        self._settings["os_autostart"] = bool(value)
        self._save()

    @property
    def power_management_enabled(self) -> bool:
        return bool(self._settings.get("power_management_enabled", True))

    @power_management_enabled.setter
    def power_management_enabled(self, value: bool):
        self._settings["power_management_enabled"] = bool(value)
        self._save()

    @property
    def power_off_on_suspend(self) -> bool:
        return bool(self._settings.get("power_off_on_suspend", True))

    @power_off_on_suspend.setter
    def power_off_on_suspend(self, value: bool):
        self._settings["power_off_on_suspend"] = bool(value)
        self._save()

    @property
    def power_off_on_lid_close(self) -> bool:
        return bool(self._settings.get("power_off_on_lid_close", True))

    @power_off_on_lid_close.setter
    def power_off_on_lid_close(self, value: bool):
        self._settings["power_off_on_lid_close"] = bool(value)
        self._save()

    @property
    def power_restore_on_resume(self) -> bool:
        return bool(self._settings.get("power_restore_on_resume", True))

    @power_restore_on_resume.setter
    def power_restore_on_resume(self, value: bool):
        self._settings["power_restore_on_resume"] = bool(value)
        self._save()

    @property
    def power_restore_on_lid_open(self) -> bool:
        return bool(self._settings.get("power_restore_on_lid_open", True))

    @power_restore_on_lid_open.setter
    def power_restore_on_lid_open(self, value: bool):
        self._settings["power_restore_on_lid_open"] = bool(value)
        self._save()

    # ---- battery saver (legacy)

    @property
    def battery_saver_enabled(self) -> bool:
        return bool(self._settings.get("battery_saver_enabled", False))

    @battery_saver_enabled.setter
    def battery_saver_enabled(self, value: bool):
        self._settings["battery_saver_enabled"] = bool(value)
        self._save()

    @property
    def battery_saver_brightness(self) -> int:
        try:
            return max(0, min(50, int(self._settings.get("battery_saver_brightness", 25) or 0)))
        except Exception:
            return 25

    @battery_saver_brightness.setter
    def battery_saver_brightness(self, value: int):
        self._settings["battery_saver_brightness"] = max(0, min(50, int(value)))
        self._save()

    # ---- power-source lighting profiles

    @property
    def ac_lighting_enabled(self) -> bool:
        return bool(self._settings.get("ac_lighting_enabled", True))

    @ac_lighting_enabled.setter
    def ac_lighting_enabled(self, value: bool):
        self._settings["ac_lighting_enabled"] = bool(value)
        self._save()

    @property
    def ac_lighting_brightness(self) -> int | None:
        v = self._settings.get("ac_lighting_brightness", None)
        if v is None:
            return None
        try:
            return self._normalize_brightness_value(v)
        except Exception:
            return None

    @ac_lighting_brightness.setter
    def ac_lighting_brightness(self, value: int | None):
        if value is None:
            self._settings["ac_lighting_brightness"] = None
        else:
            self._settings["ac_lighting_brightness"] = self._normalize_brightness_value(value)
        self._save()

    @property
    def battery_lighting_enabled(self) -> bool:
        return bool(self._settings.get("battery_lighting_enabled", True))

    @battery_lighting_enabled.setter
    def battery_lighting_enabled(self, value: bool):
        self._settings["battery_lighting_enabled"] = bool(value)
        self._save()

    @property
    def battery_lighting_brightness(self) -> int | None:
        v = self._settings.get("battery_lighting_brightness", None)
        if v is None:
            return None
        try:
            return self._normalize_brightness_value(v)
        except Exception:
            return None

    @battery_lighting_brightness.setter
    def battery_lighting_brightness(self, value: int | None):
        if value is None:
            self._settings["battery_lighting_brightness"] = None
        else:
            self._settings["battery_lighting_brightness"] = self._normalize_brightness_value(value)
        self._save()

    @property
    def per_key_colors(self) -> dict:
        """Per-key color map as {(row,col): (r,g,b)}."""
        return self._deserialize_per_key_colors(self._settings.get("per_key_colors", {}))

    @per_key_colors.setter
    def per_key_colors(self, value: dict):
        self._settings["per_key_colors"] = self._serialize_per_key_colors(value or {})
        self._save()

    # ---- screen dim sync

    @property
    def screen_dim_sync_enabled(self) -> bool:
        return bool(self._settings.get("screen_dim_sync_enabled", True))

    @screen_dim_sync_enabled.setter
    def screen_dim_sync_enabled(self, value: bool):
        self._settings["screen_dim_sync_enabled"] = bool(value)
        self._save()

    @property
    def screen_dim_sync_mode(self) -> str:
        mode = str(self._settings.get("screen_dim_sync_mode", "off") or "off").strip().lower()
        return mode if mode in {"off", "temp"} else "off"

    @screen_dim_sync_mode.setter
    def screen_dim_sync_mode(self, value: str):
        mode = str(value or "off").strip().lower()
        self._settings["screen_dim_sync_mode"] = mode if mode in {"off", "temp"} else "off"
        self._save()

    @property
    def screen_dim_temp_brightness(self) -> int:
        try:
            v = int(self._settings.get("screen_dim_temp_brightness", 5) or 0)
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
        self._settings["screen_dim_temp_brightness"] = max(1, min(50, v))
        self._save()
