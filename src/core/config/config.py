#!/usr/bin/env python3
"""KeyRGB Config implementation."""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from src.core.effects import software_targets as _software_targets

from . import defaults as _defaults
from . import file_storage as _file_storage
from . import paths as _paths
from . import perkey_colors as _perkey_colors
from ._lighting import _coercion as _lighting_coercion
from ._lighting import _lighting_accessors as _lighting_accessors
from ._lighting import _props as _lighting_props

logger = logging.getLogger(__name__)


def _normalized_optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


class Config(_lighting_accessors.LightingConfigAccessors):
    """Configuration manager for KeyRGB."""

    # Kept for backward compatibility with existing callers.
    CONFIG_DIR = _paths.config_dir()
    CONFIG_FILE = _paths.config_file_path()

    DEFAULTS = _defaults.DEFAULTS

    @staticmethod
    def _serialize_per_key_colors(color_map: dict) -> dict:
        """Convert {(row,col): (r,g,b)} -> {"row,col": [r,g,b]} for JSON."""
        return _perkey_colors.serialize_per_key_colors(color_map)

    @staticmethod
    def _deserialize_per_key_colors(data: dict) -> dict:
        """Convert {"row,col": [r,g,b]} -> {(row,col): (r,g,b)}."""
        return _perkey_colors.deserialize_per_key_colors(data)

    def __init__(self) -> None:
        # Recompute at runtime so test harnesses can set env vars in conftest.
        self.CONFIG_DIR = _paths.config_dir()
        self.CONFIG_FILE = _paths.config_file_path()
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        loaded = self._load()
        self._settings: dict[str, Any] = loaded if loaded is not None else deepcopy(self.DEFAULTS)
        self._coerce_loaded_settings()

        # Cache mtime for reload() short-circuiting.
        # Many pollers call reload() frequently; avoid re-reading JSON when the
        # file hasn't changed.
        try:
            self._last_reload_mtime_ns: int | None = self.CONFIG_FILE.stat().st_mtime_ns
        except OSError:
            self._last_reload_mtime_ns = None

    def _load(self, *, retries: int = 3, retry_delay: float = 0.02) -> dict[str, Any] | None:
        """Load settings from file.

        This may race with writers (tray/GUI) updating the JSON file. We retry a few
        times for transient JSONDecodeError (e.g., if a writer truncated then rewrote).
        Returns None if loading fails after retries.
        """

        return _file_storage.load_config_settings(
            config_file=self.CONFIG_FILE,
            defaults=self.DEFAULTS,
            retries=retries,
            retry_delay=retry_delay,
            logger=logger,
        )

    def reload(self) -> None:
        try:
            mtime_ns = self.CONFIG_FILE.stat().st_mtime_ns
        except OSError:
            mtime_ns = None

        # If the config file hasn't changed since our last successful reload,
        # skip disk I/O and JSON parsing.
        if mtime_ns is not None and self._last_reload_mtime_ns is not None:
            if int(mtime_ns) == int(self._last_reload_mtime_ns):
                return

        loaded = self._load()
        # If the file was transiently unreadable, keep the previous in-memory settings.
        if loaded is not None:
            self._settings = loaded
            self._last_reload_mtime_ns = mtime_ns

    def _save(self) -> None:
        _file_storage.save_config_settings_atomic(
            config_dir=self.CONFIG_DIR,
            config_file=self.CONFIG_FILE,
            settings=self._settings,
            logger=logger,
        )

    @staticmethod
    def _normalize_brightness_value(value: int) -> int:
        return _lighting_coercion.normalize_brightness_value(value)

    @staticmethod
    def _normalize_reactive_brightness_value(value: int) -> int:
        return _lighting_coercion.normalize_precise_brightness_value(value)

    @staticmethod
    def _normalize_reactive_trail_value(value: int) -> int:
        return _lighting_coercion.normalize_trail_percent_value(value)

    def _coerce_loaded_settings(self) -> None:
        """Coerce loaded settings into a consistent, UI-compatible shape."""

        _lighting_coercion.coerce_loaded_settings(
            settings=self._settings,
            config_file=self.CONFIG_FILE,
            save_fn=self._save,
        )

    @property
    def effect(self) -> str:
        return self._settings["effect"]

    @effect.setter
    def effect(self, value: str):
        self._settings["effect"] = value.lower()
        self._save()

    @property
    def return_effect_after_effect(self) -> str | None:
        value = _normalized_optional_string(self._settings.get("return_effect_after_effect", None))
        if value == "perkey":
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

    def get_effect_speed(self, effect_name: str) -> int:
        """Return the saved per-effect speed, falling back to the global speed."""
        speeds = self._settings.get("effect_speeds", None) or {}
        if isinstance(speeds, dict) and effect_name in speeds:
            return max(
                0,
                min(10, _lighting_accessors._coerce_int_setting(speeds[effect_name], default=self.speed)),
            )
        return self.speed

    def set_effect_speed(self, effect_name: str, speed: int) -> None:
        """Persist a per-effect speed override."""
        if not isinstance(effect_name, str):
            raise TypeError("effect_name must be a str")

        speeds = self._settings.get("effect_speeds", None)
        if not isinstance(speeds, dict):
            speeds = {}
        speeds[effect_name] = max(0, min(10, _lighting_accessors._coerce_int_setting(speed, default=0)))
        self._settings["effect_speeds"] = speeds
        self._save()

    # ---- common boolean/int settings

    autostart = _lighting_props.bool_prop("autostart", default=True)
    experimental_backends_enabled = _lighting_props.bool_prop("experimental_backends_enabled", default=False)
    os_autostart = _lighting_props.bool_prop("os_autostart", default=False)
    power_management_enabled = _lighting_props.bool_prop("power_management_enabled", default=True)
    power_off_on_suspend = _lighting_props.bool_prop("power_off_on_suspend", default=True)
    power_off_on_lid_close = _lighting_props.bool_prop("power_off_on_lid_close", default=True)
    power_restore_on_resume = _lighting_props.bool_prop("power_restore_on_resume", default=True)
    power_restore_on_lid_open = _lighting_props.bool_prop("power_restore_on_lid_open", default=True)

    # Battery saver (legacy)
    battery_saver_enabled = _lighting_props.bool_prop("battery_saver_enabled", default=False)
    battery_saver_brightness = _lighting_props.int_prop("battery_saver_brightness", default=25, min_v=0, max_v=50)

    # Power-source lighting profiles
    ac_lighting_enabled = _lighting_props.bool_prop("ac_lighting_enabled", default=True)
    battery_lighting_enabled = _lighting_props.bool_prop("battery_lighting_enabled", default=True)

    # ---- power-source lighting brightness overrides (optional)

    ac_lighting_brightness = _lighting_props.optional_brightness_prop("ac_lighting_brightness")
    battery_lighting_brightness = _lighting_props.optional_brightness_prop("battery_lighting_brightness")

    # ---- screen dim sync

    screen_dim_sync_enabled = _lighting_props.bool_prop("screen_dim_sync_enabled", default=True)
    screen_dim_sync_mode = _lighting_props.enum_prop("screen_dim_sync_mode", default="off", allowed=("off", "temp"))
    # Temp brightness is intended to be non-zero; allow 1..50.
    screen_dim_temp_brightness = _lighting_props.int_prop(
        "screen_dim_temp_brightness",
        default=5,
        min_v=1,
        max_v=50,
    )

    # Physical keyboard layout for the per-key editor / calibrator overlay.
    physical_layout = _lighting_props.enum_prop(
        "physical_layout",
        default="auto",
        allowed=("auto", "ansi", "iso", "ks", "abnt", "jis"),
    )

    software_effect_target = _lighting_props.enum_prop(
        "software_effect_target",
        default="keyboard",
        allowed=_software_targets.SOFTWARE_EFFECT_TARGETS,
    )
