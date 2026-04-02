#!/usr/bin/env python3
"""KeyRGB Config implementation."""

from __future__ import annotations

import logging
from typing import Any

from src.core.effects.software_targets import SOFTWARE_EFFECT_TARGETS
from src.core.resources.layout_legends import get_layout_legend_pack_ids, load_layout_legend_pack

from ._coercion import coerce_loaded_settings, normalize_brightness_value, normalize_rgb_triplet
from .defaults import DEFAULTS as _DEFAULTS
from .file_storage import load_config_settings, save_config_settings_atomic
from .paths import config_dir, config_file_path
from .perkey_colors import deserialize_per_key_colors, serialize_per_key_colors
from ._props import bool_prop, int_prop, enum_prop, optional_brightness_prop

logger = logging.getLogger(__name__)
_MISSING = object()


def _log_config_exception(message: str, exc: Exception) -> None:
    logger.error(message, exc, exc_info=(type(exc), exc, exc.__traceback__))


def _coerce_int_setting(value: object, *, default: int = 0) -> int:
    if value is None:
        return int(default)
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return int(default)


def _normalized_optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized or None


def _bool_setting(value: object, *, default: bool = False) -> bool:
    if value is None:
        return bool(default)
    if isinstance(value, (bool, int, float, str, list, tuple, dict, set)):
        return bool(value)
    return bool(default)


def _normalize_layout_legend_pack(value: object, *, default: str = "auto") -> str:
    normalized = str(value or default).strip().lower()
    if not normalized or normalized == "auto":
        return "auto"

    available = set(get_layout_legend_pack_ids())
    if normalized in available and load_layout_legend_pack(normalized):
        return normalized
    return str(default or "auto").strip().lower() or "auto"


def _default_setting(defaults: object, key: str, *, fallback_keys: tuple[str, ...] = (), default: object) -> object:
    if isinstance(defaults, dict):
        for candidate_key in (key, *fallback_keys):
            value = defaults.get(candidate_key, _MISSING)
            if value is not _MISSING:
                return value
        return default
    getter = getattr(defaults, "get", None)
    if not callable(getter):
        return default
    try:
        for candidate_key in (key, *fallback_keys):
            value = getter(candidate_key, _MISSING)
            if value is not _MISSING:
                return value
    except Exception as exc:
        _log_config_exception(f"Failed to read config default '{key}': %s", exc)
    return default


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

    def __init__(self) -> None:
        # Recompute at runtime so test harnesses can set env vars in conftest.
        self.CONFIG_DIR = config_dir()
        self.CONFIG_FILE = config_file_path()
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        loaded = self._load()
        self._settings: dict[str, Any] = loaded if loaded is not None else self.DEFAULTS.copy()
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

        return load_config_settings(
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
        save_config_settings_atomic(
            config_dir=self.CONFIG_DIR,
            config_file=self.CONFIG_FILE,
            settings=self._settings,
            logger=logger,
        )

    @staticmethod
    def _normalize_brightness_value(value: int) -> int:
        return normalize_brightness_value(value)

    def _coerce_loaded_settings(self) -> None:
        """Coerce loaded settings into a consistent, UI-compatible shape."""

        coerce_loaded_settings(
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
            return max(0, min(10, _coerce_int_setting(speeds[effect_name], default=self.speed)))
        return self.speed

    def set_effect_speed(self, effect_name: str, speed: int) -> None:
        """Persist a per-effect speed override."""
        try:
            effect_key = str(effect_name)
        except Exception as exc:
            _log_config_exception("Failed to normalize effect speed key: %s", exc)
            return

        speeds = self._settings.get("effect_speeds", None)
        if not isinstance(speeds, dict):
            speeds = {}
        speeds[effect_key] = max(0, min(10, _coerce_int_setting(speed, default=0)))
        self._settings["effect_speeds"] = speeds
        try:
            self._save()
        except Exception as exc:
            _log_config_exception("Failed to persist effect speed override: %s", exc)

    @property
    def brightness(self) -> int:
        # Active brightness depends on mode: per-key brightness is independent
        # from effect/uniform brightness.
        if self._settings.get("effect", "none") == "perkey":
            return _coerce_int_setting(
                self._settings.get("perkey_brightness", self._settings.get("brightness", 0)),
                default=0,
            )
        return _coerce_int_setting(self._settings.get("brightness", 0), default=0)

    @brightness.setter
    def brightness(self, value: int):
        # Preserve the other mode's brightness.
        is_perkey = self._settings.get("effect", "none") == "perkey"

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

        return _coerce_int_setting(
            self._settings.get("reactive_brightness", self._settings.get("brightness", 0)),
            default=_coerce_int_setting(self._settings.get("brightness", 0), default=0),
        )

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
    def lightbar_brightness(self) -> int:
        return _coerce_int_setting(
            self._settings.get("lightbar_brightness", self._settings.get("brightness", 0)),
            default=_coerce_int_setting(self._settings.get("brightness", 0), default=0),
        )

    @lightbar_brightness.setter
    def lightbar_brightness(self, value: int) -> None:
        self._settings["lightbar_brightness"] = self._normalize_brightness_value(value)
        self._save()

    @property
    def lightbar_color(self) -> tuple[int, int, int]:
        raw = self._settings.get("lightbar_color", None)
        if raw is None:
            raw = _default_setting(self.DEFAULTS, "lightbar_color", fallback_keys=("color",), default=[255, 0, 0])
        return normalize_rgb_triplet(raw, default=(255, 0, 0))

    @lightbar_color.setter
    def lightbar_color(self, value: tuple[int, int, int] | tuple) -> None:
        self._settings["lightbar_color"] = list(normalize_rgb_triplet(value, default=(255, 0, 0)))
        self._save()

    @property
    def direction(self) -> str | None:
        val = self._settings.get("direction", None)
        if val is None:
            return None
        return str(val).strip().lower() or None

    @direction.setter
    def direction(self, value: str | None):
        self._settings["direction"] = value
        self._save()

    @property
    def tray_device_context(self) -> str:
        raw = self._settings.get("tray_device_context", "keyboard")
        if raw is None:
            return "keyboard"
        if not isinstance(raw, str):
            return "keyboard"
        value = raw.strip().lower()
        return value or "keyboard"

    @tray_device_context.setter
    def tray_device_context(self, value: str | None) -> None:
        if value is None:
            normalized = "keyboard"
        elif isinstance(value, str):
            normalized = value.strip().lower()
        else:
            normalized = "keyboard"
        self._settings["tray_device_context"] = normalized or "keyboard"
        self._save()

    @property
    def reactive_color(self) -> tuple[int, int, int]:
        raw = self._settings.get("reactive_color", None)
        if raw is None:
            raw = _default_setting(self.DEFAULTS, "reactive_color", default=[255, 255, 255])
        return normalize_rgb_triplet(raw)

    @reactive_color.setter
    def reactive_color(self, value: tuple[int, int, int] | tuple) -> None:
        self._settings["reactive_color"] = list(normalize_rgb_triplet(value))
        self._save()

    @property
    def reactive_use_manual_color(self) -> bool:
        # Kept explicit (historically used by reactive GUI); semantics are the
        # same as a normal bool setting.
        return _bool_setting(self._settings.get("reactive_use_manual_color", False), default=False)

    @reactive_use_manual_color.setter
    def reactive_use_manual_color(self, value: bool):
        self._settings["reactive_use_manual_color"] = bool(value)
        self._save()

    @property
    def layout_legend_pack(self) -> str:
        return _normalize_layout_legend_pack(self._settings.get("layout_legend_pack", "auto"), default="auto")

    @layout_legend_pack.setter
    def layout_legend_pack(self, value: str) -> None:
        self._settings["layout_legend_pack"] = _normalize_layout_legend_pack(value, default="auto")
        self._save()

    # ---- common boolean/int settings

    autostart = bool_prop("autostart", default=True)
    experimental_backends_enabled = bool_prop("experimental_backends_enabled", default=False)
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

    # Physical keyboard layout for the per-key editor / calibrator overlay.
    physical_layout = enum_prop(
        "physical_layout",
        default="auto",
        allowed=("auto", "ansi", "iso", "ks", "abnt", "jis"),
    )

    software_effect_target = enum_prop(
        "software_effect_target",
        default="keyboard",
        allowed=SOFTWARE_EFFECT_TARGETS,
    )
