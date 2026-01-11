#!/usr/bin/env python3
"""KeyRGB Config implementation."""

from __future__ import annotations

import logging
import json
from typing import Any
from .defaults import DEFAULTS as _DEFAULTS
from .file_storage import load_config_settings, save_config_settings_atomic
from .paths import config_dir, config_file_path
from .perkey_colors import deserialize_per_key_colors, serialize_per_key_colors
from ._props import bool_prop, int_prop, enum_prop, optional_brightness_prop

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
        loaded = self._load()
        # If the file was transiently unreadable, keep the previous in-memory settings.
        if loaded is not None:
            self._settings = loaded

    def _save(self):
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

            # Detect whether the on-disk config.json explicitly contains the
            # perkey_brightness field. The loader merges defaults into the
            # loaded dict, so we can't rely on `get("perkey_brightness") is None`
            # to decide whether migration is needed.
            perkey_present_on_disk = False
            try:
                with open(self.CONFIG_FILE, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, dict) and "perkey_brightness" in raw:
                    perkey_present_on_disk = True
            except Exception:
                perkey_present_on_disk = False

            before = self._settings.get("brightness", None)
            after = self._normalize_brightness_value(before if before is not None else 0)
            if before != after:
                self._settings["brightness"] = after
                changed = True

            # Per-key brightness: keep separate from effect brightness so users
            # can use different levels and switching modes doesn't overwrite.
            perkey_before = self._settings.get("perkey_brightness", None)
            if perkey_before is None or not perkey_present_on_disk:
                # Backward-compatible migration: older configs had only
                # "brightness". When the loader merges defaults, missing keys
                # appear as the default value, so we also gate on the key being
                # absent from the on-disk JSON.
                self._settings["perkey_brightness"] = int(after)
                changed = True
            else:
                perkey_after = self._normalize_brightness_value(perkey_before)
                if perkey_before != perkey_after:
                    self._settings["perkey_brightness"] = int(perkey_after)
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
        # Active brightness depends on mode: per-key brightness is independent
        # from effect/uniform brightness.
        try:
            if str(self._settings.get("effect", "none") or "none") == "perkey":
                return int(self._settings.get("perkey_brightness", self._settings.get("brightness", 0)) or 0)
        except Exception:
            pass
        return int(self._settings.get("brightness", 0) or 0)

    @brightness.setter
    def brightness(self, value: int):
        # Preserve the other mode's brightness.
        try:
            is_perkey = str(self._settings.get("effect", "none") or "none") == "perkey"
        except Exception:
            is_perkey = False

        if is_perkey:
            self._settings["perkey_brightness"] = self._normalize_brightness_value(value)
        else:
            self._settings["brightness"] = self._normalize_brightness_value(value)
        self._save()

    @property
    def effect_brightness(self) -> int:
        """Brightness used for non-per-key effects (0..50 hardware scale)."""

        return int(self._settings.get("brightness", 0) or 0)

    @effect_brightness.setter
    def effect_brightness(self, value: int):
        self._settings["brightness"] = self._normalize_brightness_value(value)
        self._save()

    @property
    def perkey_brightness(self) -> int:
        """Brightness used for per-key mode (0..50 hardware scale)."""

        return int(self._settings.get("perkey_brightness", self._settings.get("brightness", 0)) or 0)

    @perkey_brightness.setter
    def perkey_brightness(self, value: int):
        self._settings["perkey_brightness"] = self._normalize_brightness_value(value)
        self._save()

    @property
    def reactive_brightness(self) -> int:
        """Brightness used for reactive typing pulses/highlights (0..50).

        Kept separate from `brightness` so power policies can dim the keyboard
        without overwriting the user's reactive intensity preference.

        Falls back to `brightness` for backward compatibility.
        """

        try:
            return int(self._settings.get("reactive_brightness", self._settings.get("brightness", 0)) or 0)
        except Exception:
            return int(self._settings.get("brightness", 0) or 0)

    @reactive_brightness.setter
    def reactive_brightness(self, value: int):
        self._settings["reactive_brightness"] = self._normalize_brightness_value(value)
        self._save()

    @property
    def color(self) -> tuple:
        return tuple(self._settings["color"])

    @color.setter
    def color(self, value: tuple):
        self._settings["color"] = list(value)
        self._save()

    @property
    def reactive_color(self) -> tuple[int, int, int]:
        raw = self._settings.get("reactive_color", None)
        if raw is None:
            try:
                raw = self.DEFAULTS.get("reactive_color", [255, 255, 255])
            except Exception:
                raw = [255, 255, 255]
        try:
            r, g, b = raw
        except Exception:
            r, g, b = 255, 255, 255

        def _clamp(x: Any) -> int:
            try:
                v = int(x)
            except Exception:
                return 0
            return max(0, min(255, v))

        return (_clamp(r), _clamp(g), _clamp(b))

    @reactive_color.setter
    def reactive_color(self, value: tuple[int, int, int] | tuple):
        try:
            r, g, b = value
        except Exception:
            return

        def _clamp(x: Any) -> int:
            try:
                v = int(x)
            except Exception:
                return 0
            return max(0, min(255, v))

        self._settings["reactive_color"] = [_clamp(r), _clamp(g), _clamp(b)]
        self._save()

    @property
    def reactive_use_manual_color(self) -> bool:
        # Kept explicit (historically used by reactive GUI); semantics are the
        # same as a normal bool setting.
        try:
            return bool(self._settings.get("reactive_use_manual_color", False))
        except Exception:
            return False

    @reactive_use_manual_color.setter
    def reactive_use_manual_color(self, value: bool):
        self._settings["reactive_use_manual_color"] = bool(value)
        self._save()

    # ---- common boolean/int settings

    autostart = bool_prop("autostart", default=True)
    os_autostart = bool_prop("os_autostart", default=False)
    power_management_enabled = bool_prop("power_management_enabled", default=True)
    power_off_on_suspend = bool_prop("power_off_on_suspend", default=True)
    power_off_on_lid_close = bool_prop("power_off_on_lid_close", default=True)
    power_restore_on_resume = bool_prop("power_restore_on_resume", default=True)
    power_restore_on_lid_open = bool_prop("power_restore_on_lid_open", default=True)

    # Battery saver (legacy)
    battery_saver_enabled = bool_prop("battery_saver_enabled", default=False)
    battery_saver_brightness = int_prop("battery_saver_brightness", default=25, min_v=0, max_v=50)

    # Power-source lighting profiles
    ac_lighting_enabled = bool_prop("ac_lighting_enabled", default=True)
    battery_lighting_enabled = bool_prop("battery_lighting_enabled", default=True)

    @property
    def per_key_colors(self) -> dict:
        """Per-key color map as {(row,col): (r,g,b)}."""
        return self._deserialize_per_key_colors(self._settings.get("per_key_colors", {}))

    @per_key_colors.setter
    def per_key_colors(self, value: dict):
        self._settings["per_key_colors"] = self._serialize_per_key_colors(value or {})
        self._save()

    # ---- power-source lighting brightness overrides (optional)

    ac_lighting_brightness = optional_brightness_prop("ac_lighting_brightness")
    battery_lighting_brightness = optional_brightness_prop("battery_lighting_brightness")

    # ---- screen dim sync

    screen_dim_sync_enabled = bool_prop("screen_dim_sync_enabled", default=True)
    screen_dim_sync_mode = enum_prop("screen_dim_sync_mode", default="off", allowed=("off", "temp"))
    # Temp brightness is intended to be non-zero; allow 1..50.
    screen_dim_temp_brightness = int_prop("screen_dim_temp_brightness", default=5, min_v=1, max_v=50)
